# Contributing to LLM Researcher

Thanks for your interest in contributing! 🎉 LLM Researcher is an
open-source, self-hostable **academic research assistant** — a multi-agent
pipeline that decomposes a research question, searches scholarly and web
sources in parallel, and produces a cited research document backed by a
persistent knowledge base.

This guide covers everything you need to get set up, find work, and get your
changes merged. It's a living document — if something feels out of date, feel
free to open an issue or PR.

- **License**: MIT — see [LICENSE](LICENSE)
- **Architecture**: [docs/PLAN.md](docs/PLAN.md)
- **What to work on**: [docs/ROADMAP.md](docs/ROADMAP.md)
- **Current status**: [docs/STATUS_REPORT.md](docs/STATUS_REPORT.md)

## Code of Conduct

Be kind and constructive. Harassment, discrimination, and toxic behavior of any
kind are not welcome. All contributors are expected to follow our
[Code of Conduct](CODE_OF_CONDUCT.md); see it for reporting and enforcement
details.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- An LLM API key (OpenAI/Groq/DeepSeek) **or** a local
  [Ollama](https://ollama.com/) installation
- Node.js + npm (frontend development only)
- Python 3.12 (backend development only; the repo includes `.venv`)

### Setup

```bash
cp .env.example .env
# Edit .env and configure your LLM provider (see README.md for examples)
make up        # start app, db, frontend, grobid
```

The API is then available at <http://localhost:8000/docs> (Swagger) and the
frontend at <http://localhost:3000>. See [README.md](README.md) for the full
endpoint reference and [Makefile](Makefile) for the available commands.

## Finding Work

The living task list lives in [docs/ROADMAP.md](docs/ROADMAP.md). Tasks are
organized by milestone and priority:

- **Milestone 0 (P0)** — open-source release readiness: community files,
  test/CI health, release hygiene
- **Milestone 1–3 (P1)** — reliability/UX, open workflow, academic trust
- **Milestone 4–5 (P2)** — advanced research features, production hardening
- **Backlog** — unprioritized ideas

Status legend in the roadmap: `[ ]` not started, `[~]` in progress, `[x]` done.
Pick an unstarted `[ ]` task, ideally in the highest-priority milestone, and
leave a comment or open a draft PR so others know you're working on it.

> **Heads up**: some Milestone 0 tasks exist specifically to fix known issues
> (e.g. test DB setup, `ToolResponse` generics, CI). If you're new to the
> codebase, [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) is a good
> practical re-entry guide, and [docs/STATUS_REPORT.md](docs/STATUS_REPORT.md)
> lists known issues.

## Development Workflow

1. **Fork and clone** the repository, then add the upstream remote:

   ```bash
   git clone git@github.com:<your-username>/llm-researcher.git
   cd llm-researcher
   git remote add upstream https://github.com/<upstream>/llm-researcher.git
   ```

2. **Create a feature branch** off `main`:

   ```bash
   git checkout -b feat/your-feature
   ```

3. **Make your changes**, following the conventions below.

4. **Run lint and tests** locally (see [Testing & Linting](#testing--linting)).

5. **Commit** with a descriptive message (`fix:`, `feat:`, `docs:`, `refactor:`
   prefixes are encouraged).

6. **Open a pull request** against `main`. CI runs ruff and the test suite on
   every PR; make sure it's green before requesting review.

7. **Keep PRs small and focused.** One logical change per PR makes review
   faster and history cleaner.

## Coding Conventions

### Backend (Python)

- **Stack**: FastAPI, SQLAlchemy, Pydantic v2, LangChain/LangGraph
- Use Pydantic models for all data structures (`app/schemas.py`, tool payloads)
- Use `async` functions for I/O-bound work (HTTP calls, DB access)
- Add **type hints to every function signature**
- Log via the `logging` module (DEBUG level for development) — no `print()`
- Prefer small, composable services over monolithic handlers; see
  [docs/PLAN.md](docs/PLAN.md) for the architecture
- Search sources implement the `SearchPlugin` protocol in
  `app/tools/registry.py` and are registered in `app/tools/plugins.py`

### Frontend (TypeScript/React)

- **Stack**: React + TypeScript + Vite + Tailwind CSS
- Components live in `frontend/src`; follow the existing component structure
  and naming
- Run `make frontend-dev` for hot reload or `make frontend-build` to build

### Tests

- Backend tests use **pytest** and live in `tests/` (see
  [docs/TEST_COVERAGE.md](docs/TEST_COVERAGE.md))
- Frontend tests use Vitest + React Testing Library
- When you fix a bug, add a regression test; when you add a feature, add tests
  covering the happy path and edge cases

## Testing & Linting

Use the repo-local venv (Python 3.12) or the Dockerized `make` targets:

```bash
# Tests (pytest)
.venv/bin/python -m pytest tests/ -v     # or: make test

# Lint (ruff, pinned to 0.3.4 in requirements.txt)
.venv/bin/ruff check app/                # or: make lint
```

Both `ruff check app/` and `pytest tests/` must pass locally — CI runs the
same commands (see `.github/workflows/ci.yml`). Run the full affected test
files, not just a single test, when your change touches core app code.

> **Note**: known test-suite issues (e.g. in-memory SQLite DB setup) are
> tracked as open tasks in Milestone 0 of [docs/ROADMAP.md](docs/ROADMAP.md).
> If a failure looks unrelated to your change, check the roadmap/status report
> before "fixing" it.

## Database Changes

Schema changes go through Alembic migrations:

```bash
make migration msg="describe the change"   # create a migration
make migrate                               # apply pending migrations
make migrate-down                          # roll back the last migration
```

## Documentation

Good docs are part of the feature. Update relevant docs when behavior changes:

- [docs/PLAN.md](docs/PLAN.md) — architecture and implementation history
- [docs/ROADMAP.md](docs/ROADMAP.md) — task list; mark tasks `[x]` when done
- [docs/STATUS_REPORT.md](docs/STATUS_REPORT.md) — implementation status
- [README.md](README.md) — user-facing overview and API reference

## Security & Secrets

- **Never commit API keys or secrets.** `.env` is gitignored; keep all
  credentials out of code, config, and commit messages.
- If you discover a security vulnerability, **do not open a public issue**.
  Report it privately — the security reporting process is being formalized as
  part of Milestone 0 (see [docs/ROADMAP.md](docs/ROADMAP.md)).

## Pull Request Checklist

Before submitting, confirm:

- [ ] Branch is based on the latest `main`
- [ ] `ruff check app/` passes
- [ ] `pytest tests/` passes (or failures are pre-existing and documented in
      the roadmap)
- [ ] New behavior is covered by tests
- [ ] Docs updated where relevant ([README.md](README.md),
      [docs/PLAN.md](docs/PLAN.md), [docs/ROADMAP.md](docs/ROADMAP.md), etc.)
- [ ] No secrets or local artifacts (`.env`, `test.db`, build output) are
      committed
- [ ] PR title and description clearly state the change and the roadmap task
      it addresses

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).

