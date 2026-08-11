# Test Coverage — LLM Researcher

**Last updated**: 2026-08-10

## Overview

The backend has a substantial pytest suite (~280 test functions across
`tests/`), covering state models, agents, tools, output formatting, API
routers, rate limiting, and WebSocket/researcher modules. LLM calls and
external APIs are mocked in unit tests; optional integration tests are marked
`@pytest.mark.integration`.

## Running Tests

```bash
# All tests (backend)
pytest tests/ -v

# With a coverage report
pytest tests/ --cov=app --cov-report=html

# Only integration tests
pytest -m integration
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
(`DATABASE_URL=sqlite:///:memory:`) currently reports:

```
7 failed, 273 passed, 24 errors, 1 deselected
```

### Known failures (tracked in ROADMAP Milestone 0)

1. **`tests/test_main.py` + `tests/test_integration.py`** — app-level tests
   fail with `sqlite3.OperationalError: no such table: research` because the
   app's `SessionLocal` is bound at import time to `settings.database_url`,
   and in-memory SQLite cannot be shared across connections.
2. **`tests/test_agents.py::test_intent_router_with_mocked_llm`** — mock is
   ineffective for the `__or__` special method, so the test hits the real
   OpenAI API and fails with a 401.
3. **`tests/test_tools.py::TestBibTeXParser::test_parse_empty/invalid_bibtex_string`**
   — real code bug: `ToolResponse.fail()` raises a pydantic `ValidationError`
   on unparameterized generic models.

### Notes

- The rate-limiter token-bucket test is timing-sensitive and may flake.
- Root-level legacy scripts (`test_api.py`, `test_websocket.py`,
  `test_finding_crud.py`, `test_source_crud.py`,
  `test_research_filtering.py`) predate the `tests/` layout and are scheduled
  for removal (ROADMAP Milestone 0).

## Next Steps (Testing)

See [ROADMAP.md](ROADMAP.md) Milestone 0 and Milestone 1:

1. Fix the test-DB strategy so `tests/test_main.py` and
   `tests/test_integration.py` pass in CI.
2. Fix the intent-router test to mock at the correct seam.
3. Fix the `ToolResponse` generic bug.
4. Add frontend unit tests (Vitest + Testing Library) and a Playwright smoke
   test.
5. Target ≥80% coverage for core modules (orchestrator, synthesis, routers).
