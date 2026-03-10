"""
Intent Router Agent - Classifies user messages to determine appropriate action.

This agent analyzes user messages and determines what action should be taken:
- research: Expand knowledge base with new research
- question: Answer questions about existing knowledge
- add: Manually add sources to knowledge base
- remove: Remove sources from knowledge base
- edit: Modify existing knowledge base items
- browse: Show/filter knowledge base items
- generate: Create documents from knowledge base
- status: Show current research state
"""

import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.config import settings
from app.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)


class IntentRouterOutput(BaseModel):
    """Output schema for intent classification."""

    intent: str = Field(
        description=(
            "Primary intent: research|question|add|remove|edit|"
            "browse|generate|status|general"
        )
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    entities: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Extracted entities (e.g., topic, source_url, format)"
        )
    )
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )


INTENT_ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an intent classification expert for a research
assistant system. Analyze the user's message and determine their intent.

**Intent Categories:**

1. **research** - User wants to expand knowledge base with new research
   - Examples: "Research quantum computing", "Find more about
     climate change", "Investigate recent AI developments"
   - Extract: topic (what to research)

2. **question** - User has a question about existing knowledge
   - Examples: "What does my research say about X?", "Summarize
     findings on Y", "Are there conflicting views?"
   - Extract: question_text (the question)

3. **add** - User wants to manually add a source
   - Examples: "Add this paper", "Include https://...",
     "Add this URL to my research"
   - Extract: source_url or source_reference

4. **remove** - User wants to remove a source
   - Examples: "Remove source #3", "Delete this URL",
     "This source isn't relevant"
   - Extract: source_identifier (id, url, or reference)

5. **edit** - User wants to modify knowledge base items
   - Examples: "Update notes for X", "Tag this as important",
     "Mark source Y as irrelevant"
   - Extract: item_identifier, modification_type

6. **browse** - User wants to see/filter knowledge base items
   - Examples: "Show all sources", "List papers about X",
     "What sources do I have?"
   - Extract: filter_criteria (optional)

7. **generate** - User wants to create a document
   - Examples: "Write a blog post", "Generate a summary",
     "Create an academic paper"
   - Extract: format (blog|paper|summary|custom), sections (optional)

8. **status** - User wants to see research state
   - Examples: "What's the current state?", "Show me the plan",
     "What have you done so far?"
   - Extract: None

9. **general** - General conversation or unclear intent
   - Examples: "Thanks", "Hello", "Can you help me?",
     ambiguous messages
   - Extract: None

**Guidelines:**
- Be decisive - choose the most likely intent based on keywords
  and context
- If intent is unclear, classify as "general" with low confidence
- Extract relevant entities that will help execute the intent
- Provide clear reasoning for your classification
- Confidence should be high (>0.8) for clear intents,
  lower for ambiguous ones

Respond with JSON in this exact format:
{{
    "intent": "intent_name",
    "confidence": 0.95,
    "entities": {{"key": "value"}},
    "reasoning": "explanation"
}}"""),
    ("user", "{message}")
])


def route_user_intent(message: str) -> IntentRouterOutput:
    """
    Analyze user message and determine intent.

    Args:
        message: The user's message

    Returns:
        IntentRouterOutput with classified intent and extracted entities
    """
    logger.debug(f"Routing intent for message: {message[:100]}...")

    # Get LLM provider
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.1,  # Low temperature for consistent classification
        api_key=settings.llm_api_key,
        base_url=settings.ollama_base_url,
    )

    llm = provider.get_llm()

    # Create parser
    parser = JsonOutputParser(pydantic_object=IntentRouterOutput)

    # Create chain
    chain = INTENT_ROUTER_PROMPT | llm | parser

    try:
        result = chain.invoke({"message": message})
        output = IntentRouterOutput(**result)
        logger.info(
            f"Intent classified as '{output.intent}' "
            f"with confidence {output.confidence:.2f}"
        )
        return output
    except Exception as e:
        logger.error(f"Error routing intent: {e}")
        # Fallback to general intent
        return IntentRouterOutput(
            intent="general",
            confidence=0.5,
            entities={},
            reasoning=f"Error during classification: {str(e)}"
        )
