# LLM Researcher — Architecture Plan

**Last updated**: 2026-08-10

## Overview

LLM Researcher is an open-source, self-hostable research assistant that helps
users build and explore a **persistent knowledge base**. Unlike one-shot
"research report generators", it focuses on iterative research cycles: users
submit a question, the system decomposes it, searches scholarly and web
sources, stores sources/findings/notes, and produces a cited document — while
streaming progress in real time. The AI state is persisted, so research can be
paused, resumed, and refined across sessions.

Document generation is an **optional final step** that leverages the
accumulated knowledge base.

## Core Philosophy

- **Knowledge base first**: prioritize building a rich, queryable knowledge
  base over immediate document generation.
- **User-driven exploration**: users guide research direction through
  questions, suggestions, and feedback.
- **Persistent state**: all research progress, AI reasoning, and knowledge are
  saved for future sessions.
- **API-first design**: all functionality is exposed via REST APIs and a
  WebSocket stream; the React frontend is a client of the same API.
- **Plugin-based sources**: new search providers are added by implementing a
  small `SearchPlugin` interface — no changes to the search agent.

## General Workflow

1. User provides a research query (via API or UI).
2. The **planner** decomposes it into sub-questions.
3. The **search agent** runs queries (with LLM-generated variations) across
   web and academic providers in parallel.
4. **Reference chasing** follows citations from the initial sources.
5. The **hypothesis agent** generates and ranks testable hypotheses.
6. The **synthesis agent** produces a cited draft; the **format step** filters
   references down to those actually cited.
7. Sources, findings, notes, and state are persisted; progress is streamed
   over WebSocket.

## Architecture

### Directory structure

- `app/` — backend: routers, services, agents, tools, output, NLP, memory
- `frontend/` — React + TypeScript + Vite + Tailwind UI
- `tests/` — backend test suites (pytest)
- `docs/` — architecture plan, status report, roadmap, guides
- `alembic/` — database migrations
- `deploy/` — deployment assets

### Research state (memory)

All workflow state lives in typed Pydantic models
(`app/memory/research_state.py`): sub-queries, citations, findings, notes,
hypotheses, agent steps, error log, and workflow status. State is serialized to
JSON and checkpointed to PostgreSQL after every step (`research.state_json`),
which powers resume-from-interruption and the UI's state inspector.

### Orchestrator (LangGraph)

`app/agents/orchestrator.py` defines the state machine:

```
plan → search → chase_references → hypothesize → synthesize → format → END
        │                                                     │
        └─────────────── fail (no citations) ─────────────────┘
```

Conditional edges decide whether to fail or continue; a failure node records
errors and produces a fallback document. `determine_resume_point()` inspects
existing state to resume from the last completed step.

### Agents

| Agent | File | Responsibility |
|---|---|---|
| Intent Router | `intent_router.py` | Classify user messages into research / question / add / remove / edit / browse / generate / status |
| Planner | `planner.py` | Decompose query into sub-questions |
| Query Expander | `query_expander.py` | Generate alternative phrasings per sub-query |
| Search | `search_agent.py` | Parallel searches across plugins, relevance filtering, dedup |
| Reference Chaser | `reference_chaser.py` | Follow citations from collected sources |
| Hypothesis | `hypothesis_agent.py` | Generate and rank testable hypotheses |
| Synthesis | `synthesis_agent.py` | Combine findings into a cited document |

### Tools & plugins

`app/tools/registry.py` defines the `SearchPlugin` protocol; `plugins.py`
registers built-ins at startup (enabled/disabled by configuration):

- **Web** (Tavily, DuckDuckGo fallback) · **ArXiv** · **Wikipedia**
- **Crossref** · **OpenAlex** · **PubMed** · **Semantic Scholar**
- **Springer Nature** (optional key) · **Elsevier Scopus** (optional key)
- **PDF pipeline**: download + cache, GROBID parsing, document chunking,
  BibTeX parsing
- **Web scraping**: trafilatura-based content extraction

### Data model

PostgreSQL via SQLAlchemy (see `app/models.py`, migrations in `alembic/`):

- `Research` — query, result, status, user notes, tags, `state_json`
- `ResearchSource` — collected sources/citations with notes and tags
- `ResearchFinding` — synthesized findings linked to source IDs
- `ResearchNote` — agent/user notes ("the research brain" / shared workspace)
- `ConversationMessage` — chat history
- `AppSetting` — persistent runtime settings overrides

### API & real-time

Routers live in `app/routers/` and are registered in `app/main.py`:

- `research` — lifecycle CRUD + batch / cancel / resume
- `sources`, `findings`, `notes` — knowledge-base CRUD with filtering
- `state` — state, steps, knowledge-base, entities, plan (GET/PATCH),
  document
- `chat` — conversation endpoint, history, and the WebSocket stream at
  `/ws/research/{research_id}`
- `exports` — PDF/HTML/DOCX/Markdown documents; BibTeX/CSV/JSON data
- `settings` — runtime settings overrides

A background worker (`main.py`) polls for pending tasks and executes the
workflow; `app/services/research_service.py` persists results and broadcasts
status/completion over WebSocket.

### Frontend

React + TypeScript + Vite + Tailwind. Detail view exposes **10 tabs**
(Overview, Plan, Sources, Findings, Entities, Result, Knowledge Base, Notes,
Agent Steps, Chat). The API client in `frontend/src/api/client.ts` mirrors the
backend; Nginx serves static assets and proxies `/api/` and `/ws/`.

### Deployment

Docker Compose: `app` (FastAPI), `db` (PostgreSQL 16), `frontend` (Nginx),
`grobid` (PDF parsing). See `Makefile` for `make up`, `make migrate`,
`make test`, `make lint`.

## Implementation History

Status legend: ✅ complete · 🟡 partial · ⏳ planned.

| Phase | Area | Status |
|---|---|---|
| 1 | Foundation (FastAPI, DB, Docker, LLM providers) | ✅ |
| 2 | Core tools (web, Wikipedia, ArXiv, scraping) | ✅ |
| 3 | Core agents (router, planner, search, synthesis) | ✅ |
| 4 | Orchestration (LangGraph, parallel search, checkpointing) | ✅ |
| 5 | Citation management (APA/MLA/Chicago, dedup, validation) | ✅ |
| 6 | Basic output (document, exports) | ✅ |
| 7 | Interactive knowledge-base API (findings, state, notes, tags) | ✅ |
| 8 | Extended search (Crossref, OpenAlex, PubMed, Semantic Scholar, PDF cache) | ✅ |
| 9 | PDF & document parsing (GROBID, pdfplumber, chunking, BibTeX) | ✅ |
| 10 | NLP & knowledge extraction (entities, relations) | 🟡 baseline implementations; summarizer/topic modeler remain |
| 12 | Hypothesis generation | 🟡 agent integrated into orchestrator; UI management pending |
| 16 | Real-time updates (WebSocket, cancel, resume, batch, rate limits) | ✅ |
| 19 | Web UI v1.0 | ✅ |
| 20 | Frontend v2.0 (CRUD, filtering, exports, plan/state visualization) | 🟡 bulk ops deferred; settings page unwired |

**System status**: self-hosted research workflow is operational end-to-end.
Remaining work is tracked in [ROADMAP.md](ROADMAP.md).

## Key Architecture Decisions

- **Interactive over pipeline**: designed as an interactive research
  assistant, not a one-shot generator.
- **Knowledge base first**: all artifacts stored persistently and queryable.
- **State transparency**: users can inspect AI reasoning and checkpoints.
- **Citation hygiene**: only references actually cited in the draft make it
  into the final reference list.
- **Plugin search**: adding a source = ~20 lines implementing `SearchPlugin`.

## Future Architecture Considerations

- **Knowledge graph** (Phase 11): entities/relationships enabling literature
  gap detection, contradiction identification, citation network analysis.
- **RAG pipeline**: chunk papers into embeddings for semantic retrieval and
  grounding of LLM outputs.
- **GROBID full-text**: wire parsed full text into the synthesis grounding
  path (see ROADMAP Milestone 3).
- **Multi-instance**: Redis-backed WebSocket manager and rate limiter
  (see ROADMAP Milestone 5).

## Where To Read Next

1. [ROADMAP.md](ROADMAP.md) — next tasks
2. [STATUS_REPORT.md](STATUS_REPORT.md) — current implementation status
3. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — practical re-entry guide
4. [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) — frontend architecture
