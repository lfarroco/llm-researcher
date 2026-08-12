# Test Coverage — LLM Researcher

**Last updated**: 2026-08-11

## Overview

The backend has a substantial pytest suite (~280 test functions across
`tests/`), covering state models, agents, tools, output formatting, API
routers, rate limiting, and WebSocket/researcher modules. LLM calls and
external APIs are mocked in unit tests, so the whole suite runs without
external services.

## Running Tests

```bash
# All tests (backend)
pytest tests/ -v

# With a coverage report
pytest tests/ --cov=app --cov-report=html
```

For the Dockerized flow: `make test` (runs inside the app container) and
`make lint` (ruff).

## Suite Breakdown (approx.)

| File | Focus |
|---|---|
| `tests/test_memory.py` | ResearchState, Citation, SubQueryResult, merge/reducers, serialization |
| `tests/test_output.py` | Citation formatter (APA/MLA/Chicago), references, URL validation |
| `tests/test_core.py` | Config/settings, LLM providers + factory, token-bucket rate limiter |
| `tests/test_agents.py` | Planner, search agent, intent router, query expander |
| `tests/test_tools.py` | Search tools, BibTeX parser, PDF/chunking utilities |
| `tests/test_websocket_researcher.py` | Connection manager + researcher chain |
| `tests/test_main.py` | API endpoints (health, research CRUD) |
| `tests/test_integration.py` | End-to-end API flows with mocked dependencies |
| `tests/test_entities.py`, `test_nlp_structure.py`, `test_relation_extractor.py` | NLP modules |

## Current Health

A clean-checkout run with CI-like settings
(`DATABASE_URL=sqlite:///:memory:`) passes the full suite:

```
282 passed
```

The three failures tracked in ROADMAP Milestone 0 (app-level test-DB setup,
intent-router mock seam, `ToolResponse` generic bug) were resolved, the
timing-sensitive rate-limiter test was stabilized, and the root-level legacy
scripts (`test_api.py`, `test_websocket.py`, `test_finding_crud.py`,
`test_source_crud.py`, `test_research_filtering.py`) were removed.

## Next Steps (Testing)

See [ROADMAP.md](ROADMAP.md) Milestone 1:

1. Add a Playwright smoke test for the core flows (create → monitor →
   export).
2. Target ≥80% coverage for core modules (orchestrator, synthesis, routers).
