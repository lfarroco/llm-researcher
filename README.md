# llm-researcher

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/lfarroco/llm-researcher/actions/workflows/ci.yml/badge.svg)](https://github.com/lfarroco/llm-researcher/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)

An open-source, self-hostable **academic research assistant**. Submit a
research question and llm-researcher decomposes it, searches scholarly and web
sources in parallel, and produces a cited research document — while building a
**persistent knowledge base** (sources, findings, notes, AI state) you can
explore, edit, and refine across sessions.

Built with FastAPI, LangGraph/LangChain, React, and PostgreSQL.

## ✨ Features

- **Multi-agent research pipeline**: plan → search → chase references →
  hypothesize → synthesize → format, with checkpointing, cancellation, and
  resume
- **10+ search sources**: web (Tavily/DuckDuckGo), ArXiv, Wikipedia, Crossref,
  OpenAlex, PubMed, Semantic Scholar, Springer Nature, Elsevier Scopus
- **PDF pipeline**: download + cache, GROBID parsing, chunking, BibTeX parsing
- **Full-text grounding**: open-access PDFs are parsed and chunked after search,
  so the report quotes real paper passages (stored as evidence, with character
  offsets and section labels) instead of only abstracts and search snippets
- **Idempotent knowledge base**: sources are identified by normalized DOI /
  arXiv id / URL, so re-running or resuming merges into the knowledge base
  rather than duplicating sources or discarding your notes
- **Persistent knowledge base**: sources/findings/notes CRUD with filtering,
  tags, and per-item notes
- **Real-time UI**: WebSocket progress, 10-tab detail view, plan + AI-state
  inspectors, entity extraction, chat
- **Exports**: PDF, HTML, DOCX, Markdown documents; BibTeX, CSV, JSON data
- **Bring your own model**: OpenAI, Ollama (local), Groq, or DeepSeek

## 📚 Documentation

- **[HANDOFF.md](docs/HANDOFF.md)** — start here: current state, open bugs, environment, verification
- **[ROADMAP.md](docs/ROADMAP.md)** — next tasks (milestone-based)
- **[LLM_TESTING.md](docs/LLM_TESTING.md)** — end-to-end testing guide for humans and LLM agents
- **[tasks.md](tasks.md)** — high-priority issue tracker
- **[STATUS_REPORT.md](docs/STATUS_REPORT.md)** — implementation status
- **[PLAN.md](docs/PLAN.md)** — architecture and implementation history
- **[PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)** — practical re-entry guide
- **[FRONTEND_GUIDE.md](docs/FRONTEND_GUIDE.md)** — frontend architecture
- **[TEST_COVERAGE.md](docs/TEST_COVERAGE.md)** — test suite details
- **[PHASE16_SUMMARY.md](docs/PHASE16_SUMMARY.md)** — real-time/WebSocket features
- **[QUERY_EXPANSION.md](docs/QUERY_EXPANSION.md)** — query expansion feature
- **[WORKFLOW.md](docs/WORKFLOW.md)** — open/operation-oriented workflow proposal
- **[HARNESS_FEASIBILITY.md](docs/HARNESS_FEASIBILITY.md)** — review: using DeepSeek Harness as a dependency

## 🚦 Project Status

**Beta.** The self-hosted research workflow is operational end-to-end
(research pipeline, knowledge base, real-time UI, exports). The repository is
prepared for public open-source release: community files (CONTRIBUTING, etc.)
are in place and the full test suite passes with CI-like settings. Remaining
work is tracked in the [roadmap](docs/ROADMAP.md).

## 🛠 Stack

- **Backend**: FastAPI + LangChain + LangGraph + SQLAlchemy
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Database**: PostgreSQL + Alembic migrations
- **Deployment**: Docker + Docker Compose (app, db, frontend, grobid)

## LLM Providers

Configure your preferred provider in the `.env` file:

| Provider | `.env` example |
|---|---|
| **OpenAI** | `LLM_PROVIDER=openai` · `LLM_MODEL=gpt-4o` · `OPENAI_API_KEY=...` |
| **Ollama** (local) | `LLM_PROVIDER=ollama` · `LLM_MODEL=qwen3:4b` · `OLLAMA_BASE_URL=http://localhost:11434` |
| **Groq** | `LLM_PROVIDER=groq` · `LLM_MODEL=llama-3.3-70b-versatile` · `GROQ_API_KEY=...` |
| **DeepSeek** | `LLM_PROVIDER=deepseek` · `LLM_MODEL=deepseek-flash` · `DEEPSEEK_API_KEY=...` |

Optional academic API keys enable additional search plugins:
`SPRINGER_API_KEY` (Springer Nature) and `ELSEVIER_API_KEY` (Elsevier Scopus).

## Getting Started

### Prerequisites

- Docker + Docker Compose
- An LLM API key (OpenAI/Groq/DeepSeek) **or** a local Ollama installation

### Setup

```bash
cp .env.example .env
# Edit .env and configure your LLM provider
```

### Start

```bash
make up   # start app, db, frontend, grobid
```

Pending Alembic migrations run automatically when the `app` container starts
(see the `Dockerfile` CMD), so a fresh `docker compose up` is ready to use —
no manual step required. If the DB is already running and you prefer to apply
migrations explicitly, use `make migrate` (equivalent to
`docker compose exec app alembic upgrade head`).

Then open:

- **Web UI**: http://localhost:3000
- **API docs**: http://localhost:8000/docs (Swagger) / `/redoc` (ReDoc)

## Make Commands

| Command | Description |
|---|---|
| `make up` / `make down` / `make build` / `make restart` | Compose lifecycle |
| `make logs svc=<service>` | Follow logs (`app`, `db`, `frontend`, `grobid`) |
| `make shell` / `make db-shell` | Shell into app / psql |
| `make test` | Run the test suite in the app container (isolated SQLite DB) |
| `make e2e query="..."` | End-to-end smoke test → writes to the docker-compose Postgres (`dburl` overrides) |
| `make lint` | Run ruff |
| `make migrate` / `make migration msg=...` / `make migrate-down` | Alembic |
| `make frontend-dev` | Frontend dev server (hot reload) |
| `make frontend-build` / `make frontend-install` | Frontend build/install |

## API Endpoints

Interactive docs at http://localhost:8000/docs.

### Research lifecycle
| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check |
| POST | `/research` | Create a research query |
| POST | `/research/batch` | Create multiple research queries |
| GET | `/research` | List (filters: `status`, `search`; pagination: `skip`, `limit`) |
| GET | `/research/{id}` | Get a research result |
| PATCH | `/research/{id}` | Update query / notes / tags |
| POST | `/research/{id}/cancel` | Cancel a running task |
| POST | `/research/{id}/resume` | Resume from last checkpoint |
| DELETE | `/research/{id}` | Delete |

### Knowledge base
| Method | Path | Description |
|---|---|---|
| GET/POST | `/research/{id}/sources` | List / add sources (filter by `source_type`, `tag`, `search`, `sort_by`) |
| PATCH/DELETE | `/research/{id}/sources/{source_id}` | Update / delete a source |
| GET/POST | `/research/{id}/findings` | List / create findings |
| PATCH/DELETE | `/research/{id}/findings/{finding_id}` | Update / delete a finding |
| GET/POST | `/research/{id}/notes` | List / create notes |
| PATCH/DELETE | `/research/{id}/notes/{note_id}` | Update / delete a note |

### AI state & chat
| Method | Path | Description |
|---|---|---|
| GET | `/research/{id}/state` | LangGraph agent state |
| GET | `/research/{id}/steps` | Agent execution steps |
| GET | `/research/{id}/knowledge-base` | Sources grouped by sub-query |
| GET | `/research/{id}/entities` | Extracted entities |
| GET/PATCH | `/research/{id}/plan` | View / edit the research plan |
| GET | `/research/{id}/document` | Final document |
| POST | `/research/{id}/chat` | Chat with the research results |
| GET | `/research/{id}/chat/history` | Chat history |
| WS | `/ws/research/{id}` | Real-time progress stream |

### Exports
| Method | Path | Description |
|---|---|---|
| GET | `/research/{id}/export/pdf` · `html` · `docx` · `markdown` | Document exports (pandoc) |
| GET | `/research/{id}/export/sources/bibtex` | Sources as BibTeX |
| GET | `/research/{id}/export/findings/csv` · `json` | Findings data |
| GET | `/research/{id}/export/data` | Full research data backup (JSON) |

### Runtime settings
| Method | Path | Description |
|---|---|---|
| GET | `/settings` | List effective settings (env + DB overrides) |
| PUT | `/settings/{key}` | Set a runtime override |
| DELETE | `/settings/{key}` | Clear a runtime override |

## Example

```bash
# Create a research query
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest advances in quantum computing?"}'

# Monitor progress via WebSocket (JavaScript)
const ws = new WebSocket('ws://localhost:8000/ws/research/1');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Security

Found a security vulnerability? Please report it privately — see
[SECURITY.md](SECURITY.md) for our reporting policy and expected response
times. **Do not open a public issue.**

## License

MIT — see [LICENSE](LICENSE).

