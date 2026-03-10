"""
Chat intent handlers - processes different user intents.

Each handler is a focused function that processes a single intent type,
extracted from the monolithic if/elif chain in chat_with_research.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from langchain_core.prompts import ChatPromptTemplate

from app import models
from app.config import settings
from app.llm_provider import LLMProviderFactory, rate_limited_llm_call
from app.services.research_service import process_research
from app.tools.web_scraper import scrape_url
from app.agents.synthesis_agent import (
    synthesize_findings, format_final_document,
)
from app.memory.research_state import (
    ResearchState, Citation, ResearchNote,
)

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


@dataclass
class ChatResult:
    """Result from an intent handler."""
    response_text: str
    action_taken: str
    state_changes: dict | None = None
    suggestions: list[str] | None = None


async def handle_research_intent(
    research: models.Research,
    message: str,
    entities: dict,
    background_tasks: BackgroundTasks,
    db: Session,
) -> ChatResult:
    """Handle intent: user wants to start new research."""
    topic = entities.get("topic", message)

    background_tasks.add_task(process_research, research.id, topic)

    research.status = "researching"
    db.commit()

    return ChatResult(
        response_text=(
            f"I'll start researching '{topic}' for you. "
            f"This will involve searching multiple sources and "
            f"collecting relevant information. "
            f"I'll update your knowledge base as I find new sources."
        ),
        action_taken="research_initiated",
        state_changes={"status": "researching", "new_query": topic},
        suggestions=[
            "Check research status",
            "View collected sources",
            "Ask me questions about the findings",
        ],
    )


async def handle_question_intent(
    research: models.Research,
    research_id: int,
    message: str,
    entities: dict,
    db: Session,
) -> ChatResult:
    """Handle intent: user is asking a question about existing knowledge."""
    question = entities.get("question_text", message)

    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    if not sources:
        return ChatResult(
            response_text=(
                "I don't have any sources in the knowledge base yet "
                "for this research. Would you like me to research "
                "this topic first?"
            ),
            action_taken="question_no_sources",
            suggestions=[f"Research {question}"],
        )

    # Format sources as context for the LLM
    sources_text = ""
    for i, source in enumerate(sources, 1):
        snippet = source.content_snippet or "No content available"
        sources_text += (
            f"[{i}] {source.title or 'Untitled'}\n"
            f"{snippet[:500]}\n\n"
        )

    report_context = ""
    if research.result:
        report_context = (
            f"\n\nExisting research report:\n{research.result[:3000]}"
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a research assistant. Answer the user's question "
            "based on the research sources and report provided. "
            "Cite sources using [N] format. If the sources don't "
            "contain enough information to answer, say so clearly."
        )),
        ("human",
         "Sources:\n{sources}\n{report_context}\n\nQuestion: {question}")
    ])

    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.3,
        api_key=settings.llm_api_key,
        base_url=settings.ollama_base_url,
    )
    chain = prompt | provider.get_llm()

    response = await rate_limited_llm_call(chain, {
        "sources": sources_text,
        "report_context": report_context,
        "question": question,
    })

    answer = (
        response.content if hasattr(response, 'content')
        else str(response)
    )

    return ChatResult(
        response_text=answer,
        action_taken="question_answered",
        suggestions=[
            "Ask another question",
            "View sources",
            "Regenerate report",
        ],
    )


async def handle_browse_intent(
    research: models.Research,
    research_id: int,
    db: Session,
) -> ChatResult:
    """Handle intent: user wants to see/filter knowledge base items."""
    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    if sources:
        response_text = (
            f"I found {len(sources)} source(s) in your knowledge base:\n\n"
        )
        for i, source in enumerate(sources[:5], 1):
            response_text += (
                f"{i}. [{source.source_type}] {source.title}\n"
                f"   URL: {source.url}\n\n"
            )
        if len(sources) > 5:
            response_text += f"... and {len(sources) - 5} more sources."
    else:
        response_text = (
            "Your knowledge base is currently empty. "
            "Start by asking me to research a topic or "
            "manually add sources."
        )

    return ChatResult(
        response_text=response_text,
        action_taken="browse_sources",
    )


async def handle_status_intent(
    research: models.Research,
) -> ChatResult:
    """Handle intent: user wants to see research state."""
    return ChatResult(
        response_text=(
            f"**Research Status**\n\n"
            f"Query: {research.query}\n"
            f"Status: {research.status}\n"
            f"Sources collected: {len(research.sources)}\n"
            f"Conversations: {len(research.conversations)}\n"
            f"Created: {research.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        ),
        action_taken="status_check",
        suggestions=[
            "View all sources",
            "Continue research",
            "Generate a summary",
        ],
    )


async def handle_generate_intent(
    research: models.Research,
    research_id: int,
    message: str,
    entities: dict,
    db: Session,
) -> ChatResult:
    """Handle intent: user wants to generate/regenerate a document."""
    instructions = entities.get("instructions", "")

    # Load sources from DB
    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    if not sources:
        return ChatResult(
            response_text=(
                "I can't generate a document yet because your "
                "knowledge base is empty. "
                "Please add sources or research a topic first."
            ),
            action_taken="generate_failed_no_sources",
        )

    # Convert DB sources to Citation objects for the synthesis agent
    citations = []
    for i, source in enumerate(sources, 1):
        citations.append(Citation(
            id=f"[{i}]",
            url=source.url,
            title=source.title or "Untitled",
            author=source.author or "",
            snippet=source.content_snippet or "",
            source_type=source.source_type,
            relevance_score=source.relevance_score or 0.5,
        ))

    # Load research notes from DB
    db_notes = db.query(models.ResearchNote).filter(
        models.ResearchNote.research_id == research_id
    ).all()
    research_notes = [
        ResearchNote(
            agent=n.agent, category=n.category, content=n.content
        )
        for n in db_notes
    ]

    # Add user instructions as a note to guide synthesis
    if instructions:
        research_notes.append(ResearchNote(
            agent="user",
            category="instruction",
            content=(
                f"User instruction for report generation: {instructions}"
            ),
        ))
    elif message:
        # Use the full message as instruction context
        research_notes.append(ResearchNote(
            agent="user",
            category="instruction",
            content=(
                f"User instruction for report generation: {message}"
            ),
        ))

    # Build ResearchState for the synthesis pipeline
    state = ResearchState(
        research_id=research_id,
        query=research.query,
        citations=citations,
        sub_queries=[research.query],
        research_notes=research_notes,
    )

    # Run synthesis → format pipeline
    synthesis_result = await synthesize_findings(state)

    updated_data = state.model_dump()
    updated_data.update(synthesis_result)
    updated_state = ResearchState.model_validate(updated_data)

    format_result = await format_final_document(updated_state)
    final_doc = format_result.get("final_document", "")

    # Persist regenerated report
    research.result = final_doc
    db.commit()

    instr_note = " with your instructions" if instructions else ""
    return ChatResult(
        response_text=(
            f"I've regenerated the research report{instr_note}. "
            f"The document has been updated using "
            f"{len(citations)} source(s). "
            f"You can view it in the Report tab."
        ),
        action_taken="report_generated",
        state_changes={
            "report_updated": True,
            "sources_used": len(citations),
        },
        suggestions=[
            "View the report",
            "Regenerate with different instructions",
            "Add more sources",
        ],
    )


async def handle_add_intent(
    research: models.Research,
    research_id: int,
    message: str,
    entities: dict,
    db: Session,
) -> ChatResult:
    """Handle intent: user wants to add a source or note."""
    item_type = entities.get("item_type", "")
    source_url = entities.get("source_url", "")
    note_content = entities.get("note_content", "")

    # Fallback: extract URLs from the raw message
    if not source_url:
        urls = URL_PATTERN.findall(message)
        if urls:
            source_url = urls[0]

    # --- Add a URL as a source (scrape it first) ---
    if source_url:
        try:
            scraped = await scrape_url(source_url)

            if scraped.success and scraped.content:
                source = models.ResearchSource(
                    research_id=research_id,
                    url=source_url,
                    title=(
                        scraped.title
                        or entities.get("title", "Untitled")
                    ),
                    author=scraped.author,
                    content_snippet=scraped.content[:2000],
                    source_type="web",
                    relevance_score=0.5,
                )
                db.add(source)
                db.commit()

                author_line = (
                    f"Author: {scraped.author}\n"
                    if scraped.author else ""
                )
                return ChatResult(
                    response_text=(
                        "I've added the source to your knowledge "
                        "base:\n\n"
                        f"**{scraped.title or 'Untitled'}**\n"
                        f"URL: {source_url}\n"
                        f"{author_line}"
                        f"Content preview: "
                        f"{scraped.content[:200]}..."
                    ),
                    action_taken="source_added",
                    state_changes={"source_added": source_url},
                    suggestions=[
                        "Add another source",
                        "View all sources",
                        "Regenerate report with new source",
                    ],
                )
            else:
                # Scraping failed – still record the URL
                source = models.ResearchSource(
                    research_id=research_id,
                    url=source_url,
                    title=entities.get("title", "Untitled"),
                    content_snippet=(
                        scraped.error
                        or "Content could not be extracted"
                    ),
                    source_type="web",
                    relevance_score=0.3,
                )
                db.add(source)
                db.commit()

                return ChatResult(
                    response_text=(
                        "I've added the URL to your knowledge base, "
                        "but I couldn't extract the full content: "
                        f"{scraped.error}\n\nURL: {source_url}"
                    ),
                    action_taken="source_added_partial",
                    state_changes={"source_added": source_url},
                    suggestions=[
                        "View sources",
                        "Add another source",
                    ],
                )
        except Exception as e:
            logger.error(f"Failed to scrape URL {source_url}: {e}")
            return ChatResult(
                response_text=(
                    f"I couldn't access the URL: {source_url}\n"
                    f"Error: {e}\n\n"
                    "You can try adding it manually through the "
                    "Sources tab."
                ),
                action_taken="source_add_failed",
            )

    # --- Add a note ---
    if note_content or item_type == "note":
        content = note_content or message
        note = models.ResearchNote(
            research_id=research_id,
            agent="user",
            category="note",
            content=content,
        )
        db.add(note)
        db.commit()

        return ChatResult(
            response_text=(
                f'I\'ve added your note to the research:\n\n'
                f'"{content}"'
            ),
            action_taken="note_added",
            state_changes={"note_added": True},
            suggestions=[
                "View notes",
                "Add another note",
                "Regenerate report",
            ],
        )

    # Fallback: try to detect a note from the message text
    stripped = re.sub(
        r'^(add\s+a?\s*note:?\s*|note:?\s*)',
        '', message, flags=re.IGNORECASE,
    ).strip()
    if stripped and stripped != message:
        note = models.ResearchNote(
            research_id=research_id,
            agent="user",
            category="note",
            content=stripped,
        )
        db.add(note)
        db.commit()

        return ChatResult(
            response_text=(
                f'I\'ve added your note to the research:\n\n'
                f'"{stripped}"'
            ),
            action_taken="note_added",
            state_changes={"note_added": True},
            suggestions=["View notes", "Add another note"],
        )

    return ChatResult(
        response_text=(
            "I can add sources or notes to your knowledge base. "
            "Try:\n\n"
            '- **Add a URL**: "Add https://example.com/article"\n'
            '- **Add a note**: "Add note: important finding about X"\n'
        ),
        action_taken="add_help",
        suggestions=["Add a URL", "Add a note"],
    )


async def handle_remove_intent(
    research_id: int,
    message: str,
    entities: dict,
    db: Session,
) -> ChatResult:
    """Handle intent: user wants to remove a source."""
    source_identifier = entities.get("source_identifier", "")

    source = None

    if source_identifier:
        # Try numeric ID
        try:
            match = re.search(r'\d+', str(source_identifier))
            if match:
                source_id = int(match.group())
                source = db.query(models.ResearchSource).filter(
                    models.ResearchSource.id == source_id,
                    models.ResearchSource.research_id == research_id,
                ).first()
        except (ValueError, AttributeError):
            pass

        # Try by URL
        if not source:
            source = db.query(models.ResearchSource).filter(
                models.ResearchSource.url == source_identifier,
                models.ResearchSource.research_id == research_id,
            ).first()

        # Try by title (partial match)
        if not source:
            source = db.query(models.ResearchSource).filter(
                models.ResearchSource.title.ilike(
                    f"%{source_identifier}%"
                ),
                models.ResearchSource.research_id == research_id,
            ).first()

    if source:
        title = source.title or source.url
        db.delete(source)
        db.commit()

        return ChatResult(
            response_text=f"I've removed the source: **{title}**",
            action_taken="source_removed",
            state_changes={"source_removed": title},
            suggestions=[
                "View remaining sources",
                "Add a new source",
            ],
        )

    # Couldn't find the source – list what's available
    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    if sources:
        source_list = "\n".join(
            f"- #{s.id}: {s.title or s.url}" for s in sources[:10]
        )
        return ChatResult(
            response_text=(
                "I couldn't identify which source to remove. "
                "Here are your current sources:\n\n"
                f"{source_list}\n\n"
                "Please specify the source number or title."
            ),
            action_taken="remove_source_ambiguous",
        )

    return ChatResult(
        response_text="There are no sources to remove.",
        action_taken="remove_no_sources",
    )


async def handle_edit_intent(
    research: models.Research,
    research_id: int,
    message: str,
    entities: dict,
    db: Session,
) -> ChatResult:
    """Handle intent: user wants to edit knowledge base items."""
    item_identifier = entities.get("item_identifier", "")
    modification_type = entities.get("modification_type", "")
    note_content = entities.get("note_content", "")

    # --- Adding / editing a research note ---
    if (
        modification_type in ("note", "notes")
        or "note" in message.lower()
    ):
        content = note_content or re.sub(
            r'^(edit|update|add)\s+(note|notes):?\s*',
            '', message, flags=re.IGNORECASE,
        ).strip()

        if content:
            note = models.ResearchNote(
                research_id=research_id,
                agent="user",
                category="note",
                content=content,
            )
            db.add(note)
            db.commit()

            return ChatResult(
                response_text=f'I\'ve added the note: "{content}"',
                action_taken="note_added",
                state_changes={"note_added": True},
                suggestions=["View notes", "Edit another item"],
            )

    # --- Tag a source ---
    if modification_type == "tag" and item_identifier:
        try:
            match = re.search(r'\d+', str(item_identifier))
            if match:
                source_id = int(match.group())
                source = db.query(models.ResearchSource).filter(
                    models.ResearchSource.id == source_id,
                    models.ResearchSource.research_id == research_id,
                ).first()
                if source:
                    tag = entities.get("tag", "important")
                    existing_tags = source.tags or []
                    if tag not in existing_tags:
                        existing_tags.append(tag)
                        source.tags = existing_tags
                        db.commit()
                    return ChatResult(
                        response_text=(
                            f"Tagged source '{source.title}' "
                            f"with '{tag}'."
                        ),
                        action_taken="source_tagged",
                        state_changes={"source_tagged": source_id},
                    )
        except (ValueError, AttributeError):
            pass

    # --- Update user notes on a source ---
    if item_identifier:
        source = None
        try:
            match = re.search(r'\d+', str(item_identifier))
            if match:
                source_id = int(match.group())
                source = db.query(models.ResearchSource).filter(
                    models.ResearchSource.id == source_id,
                    models.ResearchSource.research_id == research_id,
                ).first()
        except (ValueError, AttributeError):
            pass

        if source and note_content:
            source.user_notes = note_content
            db.commit()
            return ChatResult(
                response_text=(
                    f"Updated notes for source '{source.title}'."
                ),
                action_taken="source_notes_updated",
                state_changes={"source_updated": source.id},
            )

    return ChatResult(
        response_text=(
            "I can help you edit your knowledge base. Try:\n\n"
            '- **Add a note**: "Add note: finding about X"\n'
            '- **Tag a source**: "Tag source #1 as important"\n'
            '- **Update source notes**: '
            '"Update notes on source #2: ..."\n'
        ),
        action_taken="edit_help",
        suggestions=["View sources", "View notes"],
    )


async def handle_general_intent() -> ChatResult:
    """Handle intent: general conversation or unknown intent."""
    return ChatResult(
        response_text=(
            "I'm your research assistant. I can help you:\n\n"
            "- **Research** topics and collect sources\n"
            "- **Ask questions** about your research findings\n"
            "- **Add sources** by URL (I'll scrape the content)\n"
            "- **Add notes** to your research\n"
            "- **Remove** sources from your knowledge base\n"
            "- **Generate/regenerate** the report with custom "
            "instructions\n"
            "- **Browse** and manage your knowledge base\n\n"
            "What would you like to do?"
        ),
        action_taken="general_help",
        suggestions=[
            "Research a topic",
            "Show my sources",
            "Add a URL",
            "Regenerate report",
        ],
    )


async def dispatch_intent(
    intent: str,
    research: models.Research,
    research_id: int,
    message: str,
    entities: dict,
    background_tasks: BackgroundTasks,
    db: Session,
) -> ChatResult:
    """
    Dispatch a classified intent to the appropriate handler.

    Central dispatcher that routes to focused handler functions
    instead of a monolithic if/elif chain.
    """
    if intent == "research":
        return await handle_research_intent(
            research, message, entities, background_tasks, db
        )
    elif intent == "question":
        return await handle_question_intent(
            research, research_id, message, entities, db
        )
    elif intent == "browse":
        return await handle_browse_intent(research, research_id, db)
    elif intent == "status":
        return await handle_status_intent(research)
    elif intent == "generate":
        return await handle_generate_intent(
            research, research_id, message, entities, db
        )
    elif intent == "add":
        return await handle_add_intent(
            research, research_id, message, entities, db
        )
    elif intent == "remove":
        return await handle_remove_intent(
            research_id, message, entities, db
        )
    elif intent == "edit":
        return await handle_edit_intent(
            research, research_id, message, entities, db
        )
    else:
        return await handle_general_intent()
