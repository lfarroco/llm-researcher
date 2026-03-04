# Copilot Instructions for LLM Researcher

## Project Overview

This is an autonomous LLM-powered research agent that searches the web for information and produces documents with proper citations. Built with FastAPI, LangChain, and LangGraph.

## Architecture Plan

See [docs/PLAN.md](../docs/PLAN.md) for the full architecture plan, implementation phases, and technical details.

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **LLM Framework**: LangChain + LangGraph
- **Database**: PostgreSQL + SQLAlchemy
- **LLM Providers**: OpenAI (GPT-4o) or Ollama (local models)
- **Search**: Tavily API, DuckDuckGo, ArXiv, Wikipedia

## Key Concepts

### Multi-Agent Architecture
The system uses multiple specialized agents coordinated by LangGraph:
1. **Planner**: Breaks down research queries into sub-questions
2. **Search Agent**: Executes web searches in parallel
3. **Synthesis Agent**: Combines findings into coherent text
4. **Citation Agent**: Formats and validates references

### Research State
All research progress is persisted in `ResearchState` (see `app/memory/research_state.py`):
- Sub-queries derived from the main query
- Citations collected from various sources
- Findings mapped to each sub-query
- Draft document with inline citations

### Tools
Search tools in `app/tools/`:
- `web_search.py` - Tavily/DuckDuckGo web search
- `arxiv_search.py` - Academic papers
- `wikipedia.py` - Encyclopedia lookups
- `web_scraper.py` - Full page content extraction

## Code Conventions

- Use Pydantic models for all data structures
- Async functions for I/O-bound operations
- Type hints on all function signatures
- Logging via `logging` module (DEBUG level for dev)
- Tests in `tests/` directory using pytest

## Running the Project

```bash
make up          # Start Docker containers
make logs        # View application logs
make test        # Run test suite
make lint        # Run ruff linter
```

## Environment Variables

Required in `.env`:
```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

## Current Implementation Status

Refer to the checkboxes in [docs/PLAN.md](../docs/PLAN.md) for current progress.
