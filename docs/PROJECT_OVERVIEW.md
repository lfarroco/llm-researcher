# LLM Researcher - Returning Overview

Last updated: 2026-06-30

This document is a practical guide for the project.
It complements:

- `.github/copilot-instructions.md` (project intent and conventions)
- `docs/PLAN.md` (architecture and roadmap)
- `docs/STATUS_REPORT.md` (phase-level status)

## 1. What This Project Is

LLM Researcher is an API-first research assistant that:

- accepts a research question,
- decomposes it into sub-queries,
- searches multiple sources,
- synthesizes findings into a draft/final document,
- stores sources/findings/notes/state in PostgreSQL,
- streams progress in real time to a React frontend.

Core stack:

- Backend: FastAPI + LangGraph/LangChain + SQLAlchemy
- Frontend: React + TypeScript + Vite + Tailwind
- DB: PostgreSQL + Alembic migrations
- Runtime: Docker Compose

## 2. 15-Minute Restart Checklist

1. Ensure `.env` exists (`cp .env.example .env` if needed) and verify:
   - `LLM_PROVIDER` (`openai`, `ollama`, `groq`, or `deepseek`)
   - `LLM_MODEL`
   - provider API key(s)
   - optional academic keys (`SPRINGER_API_KEY`, `ELSEVIER_API_KEY`, etc.)
2. Start the stack:

   ```bash
   make up
   ```

3. Run migrations:

   ```bash
   make migrate
   ```

4. Verify services:
   - Frontend: http://localhost:3000
   - API docs: http://localhost:8000/docs
5. Run tests and lint:

   ```bash
   make test
   make lint
   ```

Useful command references are in `Makefile`.

## 3. Runtime Architecture (Current)

Entry and wiring:

- `app/main.py`
  - FastAPI app creation
  - router registration
  - background worker startup
  - default plugin registration

Research execution:

- `app/services/research_service.py`
  - `process_research_async(...)` runs a full workflow
  - persists `state_json` checkpoints during execution
  - saves sources/findings/notes to DB on completion
  - pushes status/progress/error/completion events over WebSocket

Workflow graph:

- `app/agents/orchestrator.py`
  - graph nodes: `plan -> search -> chase_references -> hypothesize -> synthesize -> format`
  - failure node and resume-point determination

Search/plugin system:

- `app/tools/registry.py` defines `SearchPlugin` protocol + registry
- `app/tools/plugins.py` registers built-ins at startup:
  - web
  - arxiv
  - wikipedia
  - springer (if key present)
  - elsevier (if key present)

## 4. Data Model Snapshot

Main ORM models in `app/models.py`:

- `Research`: query, result, status, user notes, tags, `state_json`
- `ResearchSource`: collected citations/sources
- `ResearchFinding`: synthesized findings linked to source IDs
- `ResearchNote`: agent/user notes used as long-lived research memory
- `ConversationMessage`: chat history
- `AppSetting`: runtime override settings persisted in DB

Status values encountered in code paths include:

- `pending`, `planning`, `researching`, `completed`, `failed`, `cancelled`, `error`

## 5. API Surface (High-Level)

Routers live in `app/routers/` and are mounted in `app/main.py`.

Most-used endpoints:

- Research lifecycle: create/list/get/update/cancel/resume
- Sources and findings CRUD
- State and plan inspection
- Chat against a research item
- Export endpoints (PDF/HTML/DOCX/Markdown + data exports)
- WebSocket progress stream at `/ws/research/{research_id}`

Tip: use `/docs` as the source of truth for request/response shapes.

## 6. Frontend Snapshot

Frontend app lives in `frontend/` and provides:

- research creation/list/detail
- sources/findings views
- progress monitoring
- chat interface

Important frontend entry points:

- `frontend/src/api/client.ts`
- `frontend/src/components/ResearchDetail.tsx`
- `frontend/src/components/ResearchList.tsx`

## 7. Project Status: Practical View

From code and docs combined:

- Core research pipeline is operational.
- Web UI is operational.
- Real-time progress and cancellation/resume paths exist.
- Search has a plugin architecture and multiple providers.
- Export routes are implemented (pandoc-dependent for PDF/HTML/DOCX).

Important nuance:

- `docs/PLAN.md` and `docs/STATUS_REPORT.md` are not fully synchronized on every phase label.
- The `app/nlp/` module already contains baseline implementations (not empty stubs), including rule-based extraction.

## 8. Recommended Re-Entry Work Plan

If you are coming back after months away, this is the fastest path to productive work:

1. Run smoke checks
   - `make up`, `make migrate`, `make test`, `make lint`
2. Validate end-to-end flow manually
   - create one research task from UI
   - watch WebSocket progress
   - confirm sources/findings persist
   - test one export format
3. Reconcile docs
   - align `docs/STATUS_REPORT.md` with current code reality
4. Pick one focused next milestone
   - either frontend productivity polish
   - or deeper NLP/knowledge extraction quality

## 9. Where To Read Next (In Order)

1. `.github/copilot-instructions.md`
2. `README.md`
3. `docs/PLAN.md`
4. `app/main.py`
5. `app/services/research_service.py`
6. `app/agents/orchestrator.py`
7. `app/agents/search_agent.py`
8. `app/models.py`
9. `frontend/src/components/ResearchDetail.tsx`

This sequence gives you project intent first, then runtime flow, then data model, then UI behavior.
