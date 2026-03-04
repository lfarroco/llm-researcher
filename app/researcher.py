import logging
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)


def get_researcher_chain():
    # Create provider based on configuration
    logger.debug(
        f"Setting up researcher chain with provider={settings.llm_provider}, model={settings.llm_model}"
    )
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
        base_url=settings.ollama_base_url,
    )

    llm = provider.get_llm()
    logger.debug("LLM instance retrieved from provider")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an expert researcher. Given a research query, "
                    "provide a comprehensive, well-structured answer with key findings, "
                    "analysis, and relevant context. Be thorough yet concise."
                ),
            ),
            ("human", "{query}"),
        ]
    )

    chain = prompt | llm
    logger.debug("Researcher chain created successfully")

    return chain


def run_research(query: str) -> str:
    # Truncate long queries
    logger.debug(f"Starting research for query: {query[:100]}...")
    chain = get_researcher_chain()

    logger.debug("Invoking LLM chain...")
    response = chain.invoke({"query": query})
    logger.debug(
        f"LLM response received, length: {len(response.content)} characters")

    return response.content
