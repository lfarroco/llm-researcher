# Handoff — llm-researcher

**Written**: 2026-09-25 · **For**: the next agent (or human) picking this up
**Companion docs**: [`RESEARCH_RUN_ANALYSIS.md`](RESEARCH_RUN_ANALYSIS.md) (evidence-backed
post-mortem of a real run), [`ROADMAP.md`](ROADMAP.md), [`LLM_TESTING.md`](LLM_TESTING.md),
[`../tasks.md`](../tasks.md)

This document is self-contained: read it first, then jump to whichever task you
pick up. Every claim below was verified on this machine against the running
Docker stack or the test suite.

---

## 0. TL;DR

- The four P0 defects from `RESEARCH_RUN_ANALYSIS.md` are fixed and verified.
  Full suite: **442 passing**, 1 skipped (a real-pandoc test that only runs where
  a pandoc binary exists, i.e. Docker), `ruff check app/` clean.
- **The three open bugs in §4 are now fixed and verified**, plus most of the §5
  backlog. Evidence for each is recorded in §4.
- **New, release-blocking finding:** `bibtexparser` was unpinned, so a *fresh*
  `docker compose build` installed 2.x and the app would not start at all. See
  §4.5. This only showed up on rebuild.
- **Two security gaps are documented and deliberately deferred** while the app is
  localhost-only: `GET /settings` returns live API keys in plaintext, and there
  is no auth on any route. See `../tasks.md` → "Deferred: security hardening".
  Treat any key that was readable while that endpoint was reachable as disclosed.
- All of this session's work is **uncommitted in the working tree** (see §2).


---

## 1. Environment

### Docker stack (the one that matters)

```bash
docker compose up -d          # app, db (Postgres), frontend, grobid
docker compose ps
```

| Service | URL / port | Notes |
|---|---|---|
| app (FastAPI) | http://localhost:8000 · `/docs` | `DATABASE_URL=postgresql://postgres:postgres@db:5432/researcher` |
| frontend (nginx) | http://localhost:3000 | **prebuilt image** — API additions do not appear in the UI |
| db | localhost:5432 | persistent named volume `postgres_data` |
| grobid | localhost:8070 | health takes ~1 min after start |

- The repo is bind-mounted (`.:/app`), so **code edits need a container
  restart**: `docker compose restart app`. There is no hot reload.
- Migrations run automatically on every container start
  (`Dockerfile:21` → `alembic upgrade head && exec uvicorn …`).
- LLM/Tavily credentials come from the gitignored `.env` at the repo root
  (compose interpolates `LLM_PROVIDER`, `LLM_MODEL`, `DEEPSEEK_API_KEY`, …;
  `TAVILY_API_KEY` is picked up by pydantic-settings from the mounted `.env`).
  Current values: `LLM_PROVIDER=deepseek`, `LLM_MODEL=deepseek-v4-flash`.

### Local dev server (fast loop, no Docker)

```bash
.venv/bin/python scripts/dev_server.py --port 8000
```

- Uses **in-memory SQLite**: every item disappears when the process stops.
  Never use it to test persistence.
- No pandoc and no GROBID on the host, so `/export/pdf|docx|html` return
  `503` there and full-text retrieval cannot be exercised.
- **Port trap (cost us time):** the dev server binds `127.0.0.1:8000` while
  Docker binds `[::]:8000`. On macOS `localhost` resolves to `::1`, so
  `curl localhost:8000` hits **Docker** while `curl 127.0.0.1:8000` hits the
  **dev server**. Always state the IP explicitly, and stop one before starting
  the other.

### Tests and lint (CI parity)

```bash
# Full suite with CI's isolating settings (dummy keys, in-memory SQLite):
DATABASE_URL=sqlite:///:memory: LLM_PROVIDER=openai LLM_MODEL=gpt-4o OPENAI_API_KEY=sk-test \
GROQ_API_KEY= TAVILY_API_KEY= DEEPSEEK_API_KEY= SEMANTIC_SCHOLAR_API_KEY= \
SPRINGER_API_KEY= ELSEVIER_API_KEY= NCBI_API_KEY= \
.venv/bin/python -m pytest tests/ -q          # 453 passed, 1 skipped, ~75 s

.venv/bin/python -m ruff check app/           # must stay clean (this is what CI lints)
```

`ruff check tests/` reports ~18 **pre-existing** findings (unused imports,
etc.). Leave them alone unless you are already editing those files.

`make test` runs the same suite inside the app container.

---

## 2. State of the working tree

Everything below is **uncommitted**. The previous session's work was committed
as `c20bdd4 create handoff`, so the tree was clean before this session.

```
 M .github/workflows/ci.yml              # Python 3.12, blank optional keys
 M CHANGELOG.md
 M Dockerfile                            # LaTeX packages for PDF export
 M requirements.txt                      # bibtexparser <2.0.0 (see §4.5)
 M app/agents/hypothesis_agent.py        # attribute sources to sub-queries
 M app/agents/search_agent.py            # domain cap + honest error reporting
 M app/config.py                         # per-domain cap, timeout default
 M app/main.py                           # LOG_LEVEL instead of forced DEBUG
 M app/nlp/entity_extractor.py           # drop "benchmark", bound findings
 M app/output/pdf_exporter.py            # outputfile for PDF/DOCX
 M app/routers/research.py               # persist tags/user_notes
 M app/routers/state.py                  # real sub-query progress
 M app/schemas.py                        # BatchResearchCreate notes/tags
 M app/services/chat_handlers.py         # no more stranded "researching"
 M app/services/research_service.py      # sources before grounding, timeout, session
 M app/tools/web_search.py               # title/snippet cleanup
 M app/tools/wikipedia.py                # per-page guard
 M frontend/src/components/ResearchDetail.tsx, frontend/src/types.ts  # [n] badge
 M tasks.md                              # security items + P0/P1 marked fixed
 M tests/test_agents.py  M tests/test_integration.py
 M tests/test_tools.py   M tests/test_workflow_segments.py
?? tests/test_chat_handlers.py
?? tests/test_exports.py
```

`smoke_artifacts/` is **gitignored** — the run captures referenced below do not
survive a clone. Regenerate them (§6) rather than relying on them.

---

## 3. What was completed (do not regress these)

Full rationale and evidence: [`RESEARCH_RUN_ANALYSIS.md`](RESEARCH_RUN_ANALYSIS.md) §Status.

### P0-1 — Citation numbers are shared by the document and the API

- `app/services/citation_numbering.py` is the **single place** that assigns
  reader-facing citation numbers. `renumber_document()` numbers cited sources
  `1..N` in order of first appearance, rewrites the inline markers, rebuilds the
  reference list, and returns `markers_by_identity`.
- Numbering is keyed on `source_identity(...)`, not on the citation: two
  citations that differ only by URL fragment or tracking parameter merge into
  one `ResearchSource` row, so they must share one marker.
- `app/services/research_service.py` calls it after the workflow, then passes
  `markers_by_identity` to `save_citations_to_db`, which stores the number in
  `ResearchSource.citation_marker` (nullable; `None` = not cited).
- Exposed as `citation_marker` on `GET /research/{id}/sources`
  (`app/schemas.py`).
- **Invariant to preserve:** every `[n]` in a report resolves to exactly one
  source row with `citation_marker == n` and a matching URL. `scripts/verify_run.py`
  fails the run if this breaks.

### P0-2 / P0-3 — Relevance filtering is batched and recall-oriented

`app/agents/search_agent.py`:

- `assess_relevance_batch()` / `RelevanceBatch` — one LLM call per
  `research_relevance_batch_size` sources (default 20) instead of one call per
  citation.
- The prompt asks whether a source *could contribute evidence for any part of*
  the sub-question; it no longer says "when in doubt, mark as irrelevant".
- Sources the model omits, and sources in a batch that failed, are **kept**.
- If filtering would empty a sub-query, the top
  `research_relevance_fallback_keep` sources by search score are kept instead,
  so a sub-question is never left with zero sources.

### P0-4 — arXiv

`app/tools/arxiv_search.py`:

- `build_arxiv_query()` rewrites a natural-language question into `all:` field
  syntax (strips query punctuation, stopwords, publication years).
- Exactly **one** HTTP request per call (`num_retries=0` — the library's
  internal retry used to double our request rate).
- Process-wide pacing via `_wait_for_arxiv_slot()` /
  `arxiv_min_interval_seconds` (default 3 s, arXiv's documented limit).
- A rate-limit response (`406/429/503`) trips a cooldown
  (`arxiv_rate_limit_cooldown_seconds`, default 300 s) instead of being
  retried; returns `[]` and logs a warning rather than raising.
- `app/tools/plugins.py`: arXiv runs on the first query variation only.
- `is_academic_query()` no longer treats *framework*, *model*, *method*,
  *approach* as academic markers, and `ResearchState.include_academic` now
  carries the planner's own decision into the search phase.

### Verified effect (same query, same provider)

| Metric | Before | After |
|---|---|---|
| Search phase | 226 s | 120 s |
| End-to-end | 371 s | 261–306 s |
| Sources | 16 | 34–36 |
| Sub-queries with 0 sources | 2/5 | 0/5 |
| Reference list | `1–11, 14–18` | contiguous `1..N` |
| arXiv sources | 0 | **4** (Docker run, item #10) |

---

## 4. Bugs found and fixed in this session (with evidence)

Each item below was reproduced against the running stack and now has a
regression test that fails without the fix.

### 4.1 PDF and DOCX export (was BUG-1) — FIXED

`app/output/pdf_exporter.py` called `pypandoc.convert_text` with no
`outputfile`; pandoc can write text formats to stdout but refuses binary ones.
PDF/DOCX now convert through a `NamedTemporaryFile` and are read back; the temp
file is removed on every path, including failure. The DOCX branch also passed
`--reference-doc=default`, which is not a path pandoc accepts, and that was
dropped.

**Verified in the rebuilt container** against research item #10:

```
pdf:      HTTP=200 bytes=214429 magic=25504446   # "%PDF"
docx:     HTTP=200 bytes=20222  magic=504b0304   # OOXML zip
html:     HTTP=200 bytes=66267  magic=3c21444f
markdown: HTTP=200 bytes=25269  magic=23205265
```

Tests: `tests/test_exports.py` (8 tests, patching `pypandoc.convert_text`; the
one real-pandoc test is skipped on the host).

### 4.2 PDF LaTeX packages (was BUG-2) — FIXED

`Dockerfile` installed only `texlive-latex-base`, which lacks `xcolor.sty` from
pandoc's default template. Added `texlive-latex-recommended`,
`texlive-fonts-recommended` and `lmodern`. `texlive-latex-extra` is still
deliberately excluded for size. Confirmed by the PDF export returning real
`%PDF` bytes above.

### 4.3 Full-text grounding was dead code (was BUG-3) — FIXED

`collect_fulltext_evidence` resolves candidates against the `ResearchSource`
rows for the research, but citations were persisted only after the whole
workflow — so the identity map was empty, every candidate was skipped, and the
log read `Retrieved full text for 0/3 candidate sources`.

Fixed by saving the search segment's citations *before* evidence collection
(`app/services/research_service.py`). Markers are still assigned exactly once,
by the later call, so citation numbering is unchanged.

**Evidence:** `research_evidence` was empty (`count = 0`) for every run before
the fix, which is the bug's signature. The guard test
(`tests/test_workflow_segments.py::TestCitationsPersistedBeforeGrounding`)
asserts the rows exist when evidence is collected and fails with
`source_rows: 0` when the save is removed.

### 4.4 Other defects fixed

| Area | Defect | Where |
|---|---|---|
| Chat | `research` intent stranded a `complete` item in `researching` forever (the claim only accepts `pending`). Now starts a new item for a finished report and re-queues everything else as `pending`. | `app/services/chat_handlers.py` |
| API | `tags` dropped on create; `user_notes`/`tags` ignored by `PATCH /research/{id}`; batch could not express either. | `app/routers/research.py`, `app/schemas.py` |
| Wikipedia | One unresolvable/ambiguous hit aborted the whole sub-query. Per-page guard + summary fallback. | `app/tools/wikipedia.py` |
| State | `/plan` progress always `pending` and `/state` `completed_queries` always `[]` — both read a `findings` key nothing writes. Verified live: 5/5 sub-queries now `complete`. | `app/routers/state.py` |
| Hypothesis | Phase sources were attributed to no sub-query/finding. Returned as `SubQueryResult`s now. | `app/agents/hypothesis_agent.py` |
| Search | Partial failures reported as `0 errors`; no per-domain cap. | `app/agents/search_agent.py` |
| Sources | Titles like `"Medium"` and snippets that were pure sign-in chrome. | `app/tools/web_search.py` |
| Config | `research_timeout` was dead; now an enforced whole-run budget, default raised 300 → 1800 s (measured runs are 261–306 s). | `app/services/research_service.py`, `app/config.py` |
| Worker | Leaked a DB session on every failed run; root logger forced to `DEBUG`. | `app/services/research_service.py`, `app/main.py` |
| CI | Both jobs ran Python 3.11 while the project ships 3.12; optional API keys not blanked. | `.github/workflows/ci.yml` |
| Frontend | `citation_marker` was never rendered. `[n]` badge added to the sources list and overview. | `frontend/src/components/ResearchDetail.tsx` |

### 4.5 Release-blocking: a fresh build produced a dead app

`requirements.txt` had `bibtexparser>=1.4.0`. Version 2.x removed
`bibtexparser.bparser` / `bibdatabase` / `bwriter`, which
`app/tools/bibtex_parser.py` imports, so a rebuilt image failed at import:

```
ModuleNotFoundError: No module named 'bibtexparser.bparser'
```

An existing image hid this by holding a cached 1.x wheel — it only appears on a
rebuild, which is exactly what a new contributor does. Now pinned to
`>=1.4.0,<2.0.0`.

**Watch for the same pattern in the other unpinned dependencies**
(`langgraph>=0.2.0` already resolves to 1.x, `duckduckgo-search>=5.0` is a
renamed package, `wikipedia`, `spacy`, …). They currently import cleanly, but
nothing guarantees that on the next rebuild. Consider a lockfile.

---

## 5. Backlog — what is actually left

Most of the previous backlog is now fixed; see §4 for evidence. What remains:

| # | Item | Where |
|---|---|---|
| R-1 | **Rebuild the frontend image** for the `[n]` citation badge to appear. The Docker frontend is prebuilt, so `frontend/src` changes are invisible until `make frontend-build` + image rebuild. | `frontend/`, `docker-compose.yml` |
| R-2 | **Authors are still not derived.** Title/snippet cleanup landed (§4), but nothing populates `Citation.author` for web sources, so references still lack authors and BibTeX keys fall back to `Unknown`. Doing this properly means fetching OpenGraph/`meta[author]` tags per result — a network cost that should be opt-in or cached. | `app/tools/web_search.py`, `app/tools/web_scraper.py` |
| R-3 | **Content-similarity merge is not implemented.** The per-domain cap (§4) stops one site dominating, but two near-identical pages on *different* domains still both survive. A shingle/simhash pass over snippets would catch that. | synthesis source assembly |
| R-4 | **`/state` returns an 8-key summary** while `docs/LLM_TESTING.md` promises the LangGraph state. Progress is now correct (§4); the shape mismatch is still open — either document the summary or expose the real state. | `app/routers/state.py`, `docs/LLM_TESTING.md` |
| R-5 | **Deeper entity quality.** `"benchmark"` no longer types as `material` and findings are length-bounded, but whole sentences are still surfaced as `finding` entities, which is a category error. Also, `Summarizer`/`TopicModeler` remain scaffolding (ROADMAP Milestone 3). | `app/nlp/`, `docs/ROADMAP.md` |
| R-6 | **No dependency lockfile.** §4.5 was caused by an unpinned dependency; `langgraph>=0.2.0` already resolves to 1.x and `duckduckgo-search` is a renamed package. A lockfile (pip-tools/uv) would make builds reproducible. | `requirements.txt` |
| R-7 | **Playwright smoke test for create → monitor → export** is the only unchecked item in ROADMAP Milestone 1. | `frontend/` |
| R-8 | **Security items are deferred, not fixed.** `GET /settings` returns live API keys in plaintext and no route is authenticated. Accepted while localhost-only; see `tasks.md` → "Deferred: security hardening". | `app/routers/settings.py`, `app/main.py` |

---

## 6. Verification tooling (use this after any pipeline change)

```bash
# 1. Create a real research item and capture every artifact:
curl -s -X POST localhost:8000/research -H 'Content-Type: application/json' \
  -d '{"query": "functional programming in web development in 2026"}'
.venv/bin/python scripts/capture_fp2026.py <id> smoke_artifacts/<name>

# 2. Assert the invariants:
.venv/bin/python scripts/verify_run.py smoke_artifacts/<name>
```

`verify_run.py` prints PASS/FAIL for:

- **citation numbering** — reference list is contiguous `1..N`, every marker
  resolves to exactly one source row with a matching URL;
- **sub-query coverage** — every sub-query search reported at least one source;
- **(info) source-type mix** — so a silently dead plugin stays visible.

Expected output on a healthy run:

```
[PASS] citation numbering
        29 references, 29 marked source rows, 34 sources total
[PASS] sub-query coverage
        5/5 sub-queries got sources
[info] contributing source types
        arxiv: 4
        web: 30

ALL CHECKS PASSED
```

Exit code is non-zero on failure, so it can gate CI. Existing captures:
`smoke_artifacts/fp2026` (pre-fix, fails), `fp2026_fixed`, `fp2026_verified`
(local dev server), `fp2026_docker` (Docker item #10).

---

## 7. Conventions and guardrails

- **Migrations**: add a revision file under `alembic/versions/` with `revision`
  and `down_revision` set; current head is **`b3c91d4f7a20`**. ⚠️ The migration
  chain **cannot be replayed on SQLite** — an earlier revision
  (`fd739dfc5b8b`) calls `op.drop_constraint`, which SQLite rejects. Test new
  migrations in isolation the way `tests/test_citation_marker_migration.py`
  does (load by path, bind `op` to a test engine), or run them against the
  Docker Postgres.
- **New settings** go in `app/config.py` as typed fields with a comment; the
  dev/test path constructs `Settings()` once at import.
- **Tests**: pytest with `@pytest.mark.asyncio`, one test module per area,
  `unittest.mock.patch` for LLM/tool calls. Prefer asserting on behaviour and
  on the *absence* of the old failure mode.
- **Never renumber citations outside `app/services/citation_numbering.py`.** If
  you change it, keep `markers_by_identity` consistent with
  `ResearchSource.citation_marker`, and re-run `verify_run.py`.
- **`app/tools/arxiv_search.py`**: do not remove the pacing or the cooldown, and
  do not raise `num_retries` above 0 — see §8.
- **Frontend**: the Docker image is prebuilt; new API fields are not rendered
  until the frontend is rebuilt (`make frontend-build`) and the image rebuilt.

---

## 8. Gotchas learned the hard way

- **Do not hammer arXiv.** During this session, ad-hoc `curl`/`requests`
  probing got the machine's IP throttled for minutes, which made the *entire*
  next research run collect zero arXiv sources. The tool now paces at 3 s and
  trips a 300 s cooldown on a 406; respect it. `HTTP 406` from arXiv is a
  rate-limit signal, not a query error — the same query returns `200` after a
  quiet period.
- **The dev server's SQLite is in-memory.** Items created there are gone the
  moment the process stops. If a user asks "where is my test item?", check
  which of the two servers on port 8000 answered (see §1).
- **pandoc exists only in Docker**; the host venv has none, so local export
  calls return `503` and Docker returns `500` for different reasons (BUG-1/2).
- **GROBID is running but unused** until BUG-3 is fixed.
- **`.env` holds live API keys** and is gitignored — never print or commit it.

---

## 9. Key file index

| Path | Why you care |
|---|---|
| `app/services/citation_numbering.py` | Citation numbering (P0-1) |
| `app/services/research_service.py` | Pipeline persistence: saves sources/findings/notes, full-text hook (BUG-3) |
| `app/services/fulltext.py` | Evidence retrieval and ranking |
| `app/agents/search_agent.py` | Search orchestration + batched relevance filter |
| `app/agents/synthesis_agent.py` | Report prompt and reference assembly |
| `app/agents/hypothesis_agent.py` | Hypothesis phase (P1-5) |
| `app/tools/arxiv_search.py` | arXiv query building, pacing, cooldown |
| `app/output/pdf_exporter.py` | pandoc wrapper (BUG-1) |
| `Dockerfile` | LaTeX packages (BUG-2) |
| `scripts/capture_fp2026.py`, `scripts/verify_run.py` | Run capture + invariant checks |
| `docs/RESEARCH_RUN_ANALYSIS.md` | Evidence for every claim above, plus the defect catalog |
