# LLM Researcher — Roadmap

**Last updated**: 2026-08-10

This document is the living task list for LLM Researcher. It replaces the
incremental phase numbering of the past with milestone-oriented work organized
by priority. The architecture and implementation history live in
[PLAN.md](PLAN.md); this file is strictly about *what to do next*.

Status legend:

- `[ ]` not started
- `[~]` in progress
- `[x]` done

---

## Milestone 0 — Open-Source Release Readiness (P0)

> **Goal**: Make the repository safe, legal, and welcoming to external
> contributors, and get CI green.

### License & community
- [x] Add `LICENSE` (MIT)
- [ ] Add `CONTRIBUTING.md`
- [ ] Add `CODE_OF_CONDUCT.md`
- [ ] Add `SECURITY.md`
- [ ] Add GitHub issue templates (bug report, feature request)
- [ ] Add GitHub pull request template

### Test & CI health
- [ ] Fix `ToolResponse.fail()` / `ToolResponse.ok()` generic bug
      (`app/tools/base.py`) — constructing an unparameterized generic
      `ToolResponse` raises a pydantic `ValidationError`. Currently breaks
      BibTeX parsing of empty/invalid input.
- [ ] Fix `test_intent_router_with_mocked_llm` — the mock patches the prompt's
      `__or__` on the instance, which Python never consults for special
      methods, so the test makes a real OpenAI API call and fails with a 401.
- [ ] Fix app-level test DB setup — `SessionLocal` is bound at import time to
      `settings.database_url`, so `sqlite:///:memory:` (used by CI) produces
      `no such table: research` errors in `tests/test_main.py` and
      `tests/test_integration.py`. Use a shared SQLite file fixture or a
      Postgres test service.
- [ ] Make GitHub Actions CI green (lint + full test suite).
- [ ] Remove or deprecate root-level legacy test scripts
      (`test_api.py`, `test_websocket.py`, `test_finding_crud.py`,
      `test_source_crud.py`, `test_research_filtering.py`).

### Release hygiene
- [ ] Add `CHANGELOG.md` with v2.0.0 notes.
- [ ] Add README badges (license, CI status, Python version).
- [ ] Confirm no secrets/API keys in git history.
- [ ] Tag `v2.0.0` release.

---

## Milestone 1 — Reliability & UX Completion (P1)

> **Goal**: Finish the last user-facing gaps and make the frontend testable.

- [ ] Wire `SettingsPage` into app navigation (component exists, not routed).
- [ ] Bulk operations for sources/findings (deferred Phase 20 Sprint 3).
- [ ] Pagination for sources/findings lists (backend already supports
      `skip`/`limit`).
- [ ] Tag input component with autocomplete (currently handled inline in the
      research header).
- [ ] Frontend unit tests (Vitest + React Testing Library).
- [ ] Playwright smoke test for core flows (create → monitor → export).
- [ ] Stabilize the timing-sensitive `TokenBucket` rate-limiter test.

---

## Milestone 2 — Academic Trust & Quality (P1)

> **Goal**: Make outputs verifiable and grounded so the tool is credible for
> academic use.

- [ ] Wire PDF full-text parsing (GROBID + `document_chunker`) into the
      synthesis grounding path.
- [ ] Claim-level verification: check cited sources exist and are reachable;
      flag unsupported claims.
- [ ] Citation-existence guardrail before finalizing the reference list.
- [ ] Source credibility scoring (venue/journal/peer-review signals).
- [ ] Evaluation harness + sample evaluation set for research quality.
- [ ] Finish the NLP module: real summarizer + topic modeler
      (Phase 10 remainder).
- [ ] Provenance tracking (data lineage per finding).

---

## Milestone 3 — Advanced Research Features (P2)

> **Goal**: Move from a research *collector* to a research *analyst*.

- [ ] Knowledge graph storage (Phase 11).
- [ ] Vector store / RAG over collected sources (Chroma or FAISS).
- [ ] Full-text search across the research corpus.
- [ ] Hypothesis management UI (finish Phase 12).
- [ ] Document generation from the knowledge base (Phase 15 templates:
      blog post, paper, summary).

---

## Milestone 4 — Production Hardening (P2)

> **Goal**: Support multi-user, multi-instance deployments.

- [ ] Authentication (JWT) + per-user data isolation.
- [ ] Redis-backed WebSocket manager + rate limiter (horizontal scaling).
- [ ] Structured logging + Prometheus metrics.
- [ ] Deployment guide (Docker Compose today; Kubernetes path).
- [ ] PostgreSQL backup/restore + Alembic upgrade procedures.

---

## Backlog (unprioritized ideas)

- Internationalization (i18n)
- Dark mode
- PWA / offline support
- Mobile app (React Native)
- Collaboration features (comments, activity feed, sharing)
- Scheduled re-runs / literature monitoring
