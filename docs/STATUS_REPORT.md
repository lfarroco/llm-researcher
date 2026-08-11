# LLM Researcher — Implementation Status Report

**Last updated**: 2026-08-10

## Executive Summary

LLM Researcher is an open-source, autonomous **academic research assistant**.
The core research pipeline, plugin-based search, real-time progress UI,
persistent knowledge base (sources / findings / notes), exports, and runtime
settings are all functional. The repository is in **beta**: feature-complete
for self-hosted research use, and being prepared for public open-source
release. The test suite and CI need attention before a clean `v2.0.0` tag
(see [ROADMAP.md](ROADMAP.md), Milestone 0).

## System Capabilities

### Research pipeline
- ✅ LangGraph workflow: `plan → search → chase_references → hypothesize → synthesize → format`
- ✅ Query decomposition into sub-questions (planner agent)
- ✅ Query expansion (LLM-generated query variations, configurable)
- ✅ LLM-based relevance filtering of search results
- ✅ Reference chasing (follow citations from collected sources, depth configurable)
- ✅ Hypothesis generation and ranking
- ✅ Resumable, checkpointed execution (`state_json` persisted per step)
- ✅ Cancellation and resume via API

### Search sources (plugin architecture)
- ✅ Web (Tavily with DuckDuckGo fallback)
- ✅ ArXiv (no API key required)
- ✅ Wikipedia
- ✅ Crossref, OpenAlex, PubMed, Semantic Scholar
- ✅ Springer Nature (optional key)
- ✅ Elsevier Scopus (optional key)
- ✅ PDF download + cache, GROBID parsing, document chunking, BibTeX parsing

### Knowledge base
- ✅ Sources CRUD + filtering (source type / tag / search / sort) + notes + tags
- ✅ Findings CRUD + filtering (source / search / sort)
- ✅ Notes CRUD (agent-attributed memory: planner / search / hypothesis / synthesis / user)
- ✅ Entity extraction (rule-based) + knowledge-base view
- ✅ State / plan inspection endpoints + plan editing

### API & real-time
- ✅ REST API for the full research lifecycle
  (create / batch / list / get / update / cancel / resume / delete)
- ✅ WebSocket progress stream at `/ws/research/{id}`
- ✅ Rate limiting (general + research-specific, token bucket)
- ✅ Runtime settings API (DB overrides with `.env` fallback)

### Output & export
- ✅ Research document with inline citations and a filtered reference list
- ✅ Document export: PDF, HTML, DOCX, Markdown (pandoc)
- ✅ Data export: BibTeX, CSV, JSON, full research data backup

### Frontend (React + TypeScript)
- ✅ Research list with status filtering and search
- ✅ Detail view with 10 tabs: Overview, Plan, Sources, Findings, Entities,
  Result, Knowledge Base, Notes, Agent Steps, Chat
- ✅ Full CRUD for research / sources / findings / notes
- ✅ Real-time progress, export menu, toast notifications
- 🟡 Settings page implemented but not yet wired into navigation

### LLM providers
- ✅ OpenAI, Ollama (local), Groq, DeepSeek

## Test Suite Health

Current result for a clean checkout with CI-like settings
(`DATABASE_URL=sqlite:///:memory:`):

```
7 failed, 273 passed, 24 errors, 1 deselected
```

### Known failures
1. **App-level tests** (`tests/test_main.py`, `tests/test_integration.py`):
   `sqlite3.OperationalError: no such table: research`. The app's
   `SessionLocal` is bound at import time to `settings.database_url`, and the
   in-memory SQLite database cannot be shared across connections. Requires a
   test-DB strategy fix (ROADMAP Milestone 0).
2. **`test_intent_router_with_mocked_llm`**: makes a real OpenAI API call
   (the mock patches `__or__` on the instance, which Python never consults for
   special methods) and fails with a 401.
3. **`TestBibTeXParser::test_parse_empty/invalid_bibtex_string`**: real code
   bug — `ToolResponse.fail()` raises a pydantic `ValidationError` when called
   on an unparameterized generic model.

All three are tracked in [ROADMAP.md](ROADMAP.md) Milestone 0.

## Not Implemented Yet

- Knowledge graph storage
- Vector store / RAG over collected sources
- Full-text search across the research corpus
- Document generation templates from the KB (blog / paper / summary)
- Authentication / multi-user support
- End-to-end evaluation of research output quality

## Deployment

- **Docker Compose services**: `app` (FastAPI), `db` (PostgreSQL 16),
  `frontend` (Nginx), `grobid` (PDF parsing)
- **Commands**: `make up`, `make migrate`, `make test`, `make lint`,
  `make logs`
- **Access**: UI http://localhost:3000 · API http://localhost:8000/docs

## Next Steps

See [ROADMAP.md](ROADMAP.md). Short term: **Milestone 0** — OSS release
readiness (community files, green CI, release hygiene).
