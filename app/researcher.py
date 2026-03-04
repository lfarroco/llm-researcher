from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from app.config import settings


def get_researcher_chain():
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0.2,
    )

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

    return chain


def run_research(query: str) -> str:
    chain = get_researcher_chain()
    response = chain.invoke({"query": query})
    return response.content
