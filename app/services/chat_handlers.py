"""
Chat intent handlers - processes different user intents.

Each handler is a focused function that processes a single intent type,
extracted from the monolithic if/elif chain in chat_with_research.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from app import models
from app.services.research_service import process_research

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """Result from an intent handler."""
    response_text: str
    action_taken: str
    state_changes: dict | None = None
    suggestions: list[str] | None = None


def handle_research_intent(
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


def handle_question_intent(
    research: models.Research,
    message: str,
    entities: dict,
    db: Session,
) -> ChatResult:
    """Handle intent: user is asking a question about existing knowledge."""
    question = entities.get("question_text", message)
    source_count = len(research.sources)

    if source_count > 0:
        return ChatResult(
            response_text=(
                f"I found {source_count} source(s) in your knowledge base. "
                "Based on the collected research, I'll analyze the "
                "information and provide an answer. "
                "(Note: Full RAG implementation coming soon)"
            ),
            action_taken="question_answered",
        )

    return ChatResult(
        response_text=(
            "I don't have any sources in the knowledge base yet "
            "for this research. Would you like me to research "
            "this topic first?"
        ),
        action_taken="question_no_sources",
        suggestions=[f"Research {question}"],
    )


def handle_browse_intent(
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


def handle_status_intent(
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


def handle_generate_intent(
    research: models.Research,
    entities: dict,
) -> ChatResult:
    """Handle intent: user wants to generate a document from knowledge base."""
    format_type = entities.get("format", "summary")

    if len(research.sources) == 0:
        return ChatResult(
            response_text=(
                "I can't generate a document yet because your "
                "knowledge base is empty. "
                "Please add sources or research a topic first."
            ),
            action_taken="generate_failed_no_sources",
        )

    return ChatResult(
        response_text=(
            f"I'll generate a {format_type} from your knowledge base. "
            f"This will synthesize information from "
            f"{len(research.sources)} source(s). "
            f"(Note: Full generation implementation coming soon)"
        ),
        action_taken="generate_initiated",
        state_changes={"generating": format_type},
    )


def handle_add_intent() -> ChatResult:
    """Handle intent: user wants to manually add a source."""
    return ChatResult(
        response_text=(
            "I can help you add sources to your knowledge base. "
            "Please provide the URL or reference. "
            "(Note: Manual source addition coming soon)"
        ),
        action_taken="add_source_requested",
    )


def handle_remove_intent() -> ChatResult:
    """Handle intent: user wants to remove a source."""
    return ChatResult(
        response_text=(
            "I can help you remove sources from your knowledge base. "
            "(Note: Source removal coming soon)"
        ),
        action_taken="remove_source_requested",
    )


def handle_edit_intent() -> ChatResult:
    """Handle intent: user wants to edit knowledge base items."""
    return ChatResult(
        response_text=(
            "I can help you edit items in your knowledge base. "
            "(Note: Editing functionality coming soon)"
        ),
        action_taken="edit_requested",
    )


def handle_general_intent() -> ChatResult:
    """Handle intent: general conversation or unknown intent."""
    return ChatResult(
        response_text=(
            "I'm your research assistant. I can help you:\n\n"
            "• Research topics and collect sources\n"
            "• Answer questions about your research\n"
            "• Browse and manage your knowledge base\n"
            "• Generate documents from your research\n\n"
            "What would you like to do?"
        ),
        action_taken="general_help",
        suggestions=[
            "Research a topic",
            "Show my sources",
            "Check status",
        ],
    )


# Maps intent strings to their handler metadata for dispatch
INTENT_HANDLERS = {
    "research": "handle_research_intent",
    "question": "handle_question_intent",
    "browse": "handle_browse_intent",
    "status": "handle_status_intent",
    "generate": "handle_generate_intent",
    "add": "handle_add_intent",
    "remove": "handle_remove_intent",
    "edit": "handle_edit_intent",
    "general": "handle_general_intent",
}


def dispatch_intent(
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
        return handle_research_intent(
            research, message, entities, background_tasks, db
        )
    elif intent == "question":
        return handle_question_intent(research, message, entities, db)
    elif intent == "browse":
        return handle_browse_intent(research, research_id, db)
    elif intent == "status":
        return handle_status_intent(research)
    elif intent == "generate":
        return handle_generate_intent(research, entities)
    elif intent == "add":
        return handle_add_intent()
    elif intent == "remove":
        return handle_remove_intent()
    elif intent == "edit":
        return handle_edit_intent()
    else:
        return handle_general_intent()
