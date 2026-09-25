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

- The four P0 defects from `RESEARCH_RUN_ANALYSIS.md` are **fixed, tested, and
  verified end-to-end**. Full suite: **404 passing**, `ruff check app/` clean.
- **Nothing is committed.** All work is in the working tree (see §2).
- **Three bugs remain open, all newly discovered and all with a known root
  cause**: binary document exports (PDF/DOCX), missing LaTeX packages in the
  Docker image, and full-text grounding being dead code. See §4.
- Then there is a queue of P1/P2 work in §5.

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
.venv/bin/python -m pytest tests/ -q          # 404 passed, ~60 s

.venv/bin/python -m ruff check app/           # must stay clean (this is what CI lints)
```

`ruff check tests/` reports ~18 **pre-existing** findings (unused imports,
etc.). Leave them alone unless you are already editing those files.

`make test` runs the same suite inside the app container.

---

## 2. State of the working tree

Uncommitted (all of it is intended work from the last session):

```
 M CHANGELOG.md
 M app/agents/planner.py                 # returns include_academic
 M app/agents/search_agent.py            # batched, recall-oriented relevance filter
 M app/agents/synthesis_agent.py         # uses shared reference-line formatter
 M app/config.py                         # new settings (see §3)
 M app/memory/research_state.py          # ResearchState.include_academic
 M app/models.py                         # ResearchSource.citation_marker
 M app/schemas.py                        # ResearchSourceResponse.citation_marker
 M app/services/research_service.py      # renumber + persist markers
 M app/tools/arxiv_search.py             # query building, pacing, cooldown
 M app/tools/plugins.py                  # arXiv first-variation-only
 M tests/test_agents.py  M tests/test_tools.py
?? alembic/versions/b3c91d4f7a20_add_citation_marker_to_sources.py
?? app/services/citation_numbering.py
?? tests/test_citation_numbering.py
?? tests/test_citation_marker_migration.py
?? docs/RESEARCH_RUN_ANALYSIS.md
?? scripts/capture_fp2026.py
?? scripts/verify_run.py
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

## 4. Open bugs (start here)

### BUG-1 — PDF and DOCX export always fail (HTTP 500)

**Repro** (Docker):

```bash
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/research/10/export/docx   # 500
curl -s localhost:8000/research/10/export/pdf
# {"detail":"Failed to export PDF: Pandoc conversion failed: Output to pdf only works by using a outputfile."}
```

**Root cause**: `app/output/pdf_exporter.py:116-128` calls
`pypandoc.convert_text(md, output_format.value, format='md', extra_args=…)`
with **no `outputfile`**. Pandoc can write text formats (html, markdown) to
stdout, but refuses binary formats:

```
docx stdout -> RuntimeError: Output to docx only works by using a outputfile.
docx file   -> OK (9706 bytes)          # verified inside the container
```

**Fix**: in `export_markdown_to_format`, for binary formats (`ExportFormat.PDF`,
`ExportFormat.DOCX`) convert into a
`tempfile.NamedTemporaryFile(suffix="." + fmt.value, delete=False)`, read the
bytes back, delete the file, and return them. Keep the stdout path for
HTML/MARKDOWN.

**Also check**: the DOCX branch passes `--reference-doc=default` (line ~104).
Pandoc expects a real `.docx` path there; validate whether it must be dropped
or replaced with a bundled template.

**Tests**: there are currently **no** pandoc/export tests in `tests/`. Add unit
tests that patch `pypandoc.convert_text` and assert (a) `outputfile` is passed
for docx/pdf, (b) the returned bytes equal the temp file's contents, and
(c) text formats still use the stdout path. Guard any real-pandoc test with
`pytest.mark.skipif(not check_pandoc_installed())`, because the host venv has
no pandoc.

### BUG-2 — PDF needs LaTeX packages the image does not install

With BUG-1 fixed, PDF still fails inside the container:

```
! LaTeX Error: File `xcolor.sty' not found.
```

**Root cause**: `Dockerfile:6-11` installs `texlive-latex-base` only ("to
reduce size"), but pandoc's default LaTeX template needs packages shipped in
`texlive-latex-recommended` / `texlive-fonts-recommended` (`xcolor.sty` is one
of them).

**Fix (pick one)**:
1. Add `texlive-latex-recommended texlive-fonts-recommended` (and
   `texlive-latex-extra` for full coverage) to the `apt-get install`; rebuild
   with `docker compose build app && docker compose up -d app`. Costs image
   size — the existing comment shows the tradeoff was deliberate.
2. Keep the image small and document that PDF export requires extra packages.
3. Switch `--pdf-engine` to something with a smaller dependency set.

**Acceptance**: `curl -s -o /tmp/o.pdf -w '%{http_code}\n'
localhost:8000/research/10/export/pdf` → `200` and the file starts with `%PDF`.

### BUG-3 — Full-text grounding never engages (dead code)

**Evidence** (container log, item #10):

```
[FULLTEXT] Retrieved full text for 0/3 candidate sources
[FULLTEXT] 0 evidence span(s) available for synthesis
[SYNTHESIS] No full-text evidence available; writing from search excerpts only
```

Three arXiv candidates were correctly selected, then every one was skipped.

**Root cause**: `collect_fulltext_evidence` resolves candidates against
`ResearchSource` rows that already exist in the DB
(`app/services/fulltext.py:329-343`), but in `process_research_async` it is
called at `app/services/research_service.py:394` — *before* any row is written,
because `save_citations_to_db` only runs at line 447, after the whole workflow.
The identity map is therefore empty, `source` is `None`, and every candidate
hits `continue`.

**Fix**: persist the citations as soon as the search segment finishes and
**before** evidence collection — i.e. right after
`run_research_workflow(..., interrupt_after=["chase_references"])` (line 385)
and before line 394:

```python
save_citations_to_db(db, research_id, search_state.citations)  # no markers yet
db.commit()
```

Keep the existing call at line 447 **with** `markers_by_identity` — it is an
idempotent identity merge, and it is what assigns the citation markers. Passing
no markers in the early call is deliberate so markers are only written once.
Side benefit: sources appear in the knowledge base while the run is still
going.

**Acceptance**:
- Container log shows `[FULLTEXT] Retrieved full text for N/M candidate sources`
  with `N > 0` on a topic that yields arXiv sources.
- `docker compose exec db psql -U postgres -d researcher -c 'select count(*) from research_evidence;'` > 0.
- The synthesis step logs `[SYNTHESIS] Grounding in … full-text passage(s)`.
- `scripts/verify_run.py` still passes (numbering unchanged).

**Test**: `tests/test_fulltext_grounding.py` already covers chunk ranking and
selection. Add a test that `process_research_async` persists citations before
calling `collect_fulltext_evidence` — patch both functions and assert call
order (or assert the evidence function received a non-empty DB).

---

## 5. Backlog (from the run analysis and the issue tracker)

Ordered by value; see `RESEARCH_RUN_ANALYSIS.md` and `tasks.md` for full repro
steps and evidence.

| # | Item | Where |
|---|---|---|
| P1-1 | Wikipedia aborts a whole search on one bad page title (`PageError: Page id "function programming" does not match any pages`, `DisambiguationError: "Scale"`, `"Complex"`). Wrap each page fetch; fall back to `wikipedia.summary(query, auto_suggest=True)`. | `app/tools/wikipedia.py:53-66` |
| P1-4 | `/research/{id}/plan` progress is **always** `pending` **and** `/research/{id}/state` reports `completed_queries: []` — both read `state_json["findings"]`, which nothing ever writes. Populate them from `sub_query_results` or from the persisted findings. (Two call sites, one root cause.) Also `/state` returns an 8-key summary while the docs promise the LangGraph state. | `app/routers/state.py:68` and `:290-307`, `docs/LLM_TESTING.md` |
| P1-5 | Sources found by the hypothesis phase carry the report's most specific claims but are linked to **no** sub-query or finding (findings < sub-questions). Return them as a `SubQueryResult`/finding. | `app/agents/hypothesis_agent.py:635` |
| P1-2/P1-3 | Poor source metadata and boilerplate snippets: reference titles like `"Medium"` and `"2 Technology"`, no authors anywhere, BibTeX keys like `@misc{Unknown2026Medium}` whose abstract is sign-in chrome. Derive titles/authors from OpenGraph/URL slug and strip leading boilerplate before assessing relevance. | `app/tools/web_search.py`, `app/agents/search_agent.py` |
| P2-1 | No domain cap: 4 near-duplicate `pkgpulse.com` pages were the most-cited sources in one report. Add a per-domain cap and content-similarity merge. | synthesis source assembly |
| P2-2 | `research_timeout` is dead configuration; cancellation is only checked before/after the whole workflow. | `app/config.py:35`, `app/services/research_service.py` |
| P2-3 | `tasks.md` P0 (chat intent flips a completed item to `researching` forever) and P1 (`tags`/`user_notes` silently dropped) — **both still reproduce**. | `app/services/chat_handlers.py`, `app/routers/research.py` |
| P2-4 | Meaningless entities (`"benchmark"` typed `material`; a 160-char sentence typed `finding`), search summary reporting `0 errors` while two sub-query steps are `error`. | `app/nlp/entity_extractor.py`, `app/agents/search_agent.py` |

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
