# DeepSeek Harness as a Dependency — Feasibility Review

**Date**: 2026-09-25
**Status**: Review / recommendation — no code changed
**Verdict**: Technically feasible, but **not worth it as a wholesale replacement
today**. More importantly, the DSH question is the wrong first question: the
project has data-integrity bugs and an evidence-model gap that dominate any
runtime choice (see §8-§9).

---

## 1. Executive summary

The intuition behind the question is correct in kind but not in magnitude.

- The parts of this repo that a general-purpose agent harness duplicates are the
  **smallest** parts: roughly **2,700 LOC of 21,000 backend LOC** (~13%), plus
  ~740 LOC of web acquisition and ~250 LOC of chat routing.
- The parts that make this project *a research tool* — the academic search
  plugins, PDF/GROBID parsing, BibTeX, reference chasing, citation formatting,
  the knowledge base — are **not** provided by any general harness
  (~8,000 LOC), and they are framework-free: `grep -rn langchain app/tools/
  app/nlp/` returns **zero** matches.
- Meanwhile the project's own roadmap ([ROADMAP.md](ROADMAP.md) Milestone 3)
  says the *value* gap is academic trust and quality: claim verification, source
  credibility, provenance, an evaluation harness. All of that is still
  unbuilt. Swapping the plumbing for a harness would consume the budget that
  Milestone 3 needs and produce no new research capability.

So: adding DeepSeek Harness (DSH) as a dependency is **feasible** — there is an
official Python SDK, the domain tools are already framework-free and
MCP-mountable, and the interfaces line up better than expected. But the
recommended posture is **do not refactor onto it now**; instead adopt it behind
a seam, starting with the one job it does strictly better than the current code
(open-ended web acquisition), and revisit full delegation when three specific
blockers clear (§7).

While doing this review I audited the pipeline itself, and that audit changed the
recommendation's ordering. Four findings outrank the harness question entirely
(detail in §8):

1. **Resume deletes the user's knowledge base** — including user-authored notes,
   tags, and source annotations (`research_service.py:196-209`).
2. **Synthesis never reads paper text** — the entire report is written from
   1,200-character search snippets; the 1,300-LOC PDF pipeline has no production
   consumer.
3. **There is no claim-level provenance in the data model**, so the roadmap's
   verification and credibility goals have nowhere to live.
4. **No evaluation exists**, so no architectural change — harness or otherwise —
   can be validated.

---

## 2. What was reviewed

| Item | Version / detail |
|---|---|
| Project | `/Users/momo/dev/llm-researcher`, FastAPI + LangGraph + React, last commit 2026-08-14 |
| Backend size | 21,003 Python LOC (`app/` + `scripts/` + `tests/`); frontend 5,914 LOC |
| DSH CLI | `@deepseek-ai/dsh` **0.1.5-rc.3** (local npx checkout) |
| DSH Python SDK | `deepseek-harness-sdk` **0.1.5rc1** from PyPI (installed and inspected in a scratch venv) |
| DSH bundled runtime | `deepseek-harness-runtime-bin` **0.1.5rc1** — 72–80 MB wheel per platform, ~267 MB unpacked, no system Node.js required |
| Method | Read the DSH profile compositions (`dsh-base`, `dsh-sdk-app`), the SDK server/protocol docs, the installed Python SDK source, and inventoried the project's own modules with line counts |

---

## 3. What this project is actually made of

Three layers, with different reusability under DSH.

### A. Generic agent-runtime plumbing — replaceable (~2,700 LOC)

| File | LOC | What DSH already does |
|---|---|---|
| `app/llm_provider.py` | 328 | Model routing + provider adapters (`dsh-llm`, `dsh-llm-deepseek`, `dsh-llm-pi-ai`), retries (`dsh-llm-retry`) |
| `app/agents/orchestrator.py` | 291 | Agent loop + streaming (`dsh-agent`, `dsh-agent-loop`) |
| `app/services/research_service.py` | 319 | Session lifecycle, persistence, progress fanout (`dsh-session`, JSONL persistence, event stream) |
| `app/memory/research_state.py` | 277 | Conversation/state persistence + resume (sessions, checkpoint policy) |
| `app/rate_limiter.py` | 209 | Partly redundant (HTTP layer stays; LLM back-pressure is `dsh-llm-retry` + token meter) |
| `app/websocket_manager.py` | 145 | Progress streaming (`session.event` / `session.status` notifications) |
| `app/agents/intent_router.py` | 180 | Tool selection — the harness's native function-calling replaces intent classification |
| `app/agents/query_expander.py` | 137 | A one-turn LLM call; trivial under a harness |
| `app/tools/web_scraper.py` | 138 | `web_fetch` |
| `app/tools/web_search.py` | 164 | `web_search` (DeepSeek search, with Tavily/DDG currently) |
| `app/tools/wikipedia.py` | 90 | `web_fetch`/`web_search` |
| `app/tools/pdf_download.py` | 347 | Mostly URL→hash cache + size cap; `web_fetch` + a small helper covers the retrieval half |
| `app/researcher.py` | 55 | A standalone ad-hoc chain; unused by the graph |

Plus `app/services/chat_handlers.py` (739 LOC) is **mixed**: its dispatch half
`handle_research_intent`-style routing is exactly what a harness does; its
handler half is real application logic (DB CRUD, note/tag editing, report
generation) and must stay.

### B. Domain research value — keep (~8,000 LOC)

| Area | Files | LOC |
|---|---|---|
| Academic search APIs + normalization | arXiv, Crossref, OpenAlex, PubMed, Semantic Scholar, Springer, Elsevier | ~2,100 |
| Bibliographic parsing | `bibtex_parser.py` | 452 |
| Scholarly PDF | `pdf_parser.py` (GROBID TEI), `document_chunker.py` | 958 |
| Citation/reference extraction | `reference_extractor.py` | 390 |
| Research NLP | `entity_extractor.py`, `relation_extractor.py` | 363 |
| Research prompts/pipeline | planner, search, hypothesis, synthesis, reference chaser | 2,200 |
| Citation formatting / exports | `citation_formatter.py` | 411 |

**Critical property**: this layer has **no LangChain coupling**. The plugin
contract is a duck-typed `typing.Protocol` (`app/tools/registry.py:32-69`) whose
methods are plain `async def search(query, max_results) -> list[Citation]`, where
`Citation` is a Pydantic model. It is callable from any Python process, and its
shape is already MCP-tool-shaped.

### C. Application/API layer — keep (~1,100 LOC)

SQLAlchemy models, Pydantic schemas, routers, Alembic migrations, service
helpers. Unaffected by harness choice; it is the product's persistence and API
contract. (The frontend consumes only `/research*` REST routes plus the
WebSocket, so it is insulated from the backend's agent runtime.)

---

## 4. What DSH actually offers

### The `sdk` profile roster (from `dsh-base/cordis.patch.yml`)

Already present, no work required:

- **Files**: `read`, `write`, `edit`, `glob`, `grep`
- **Shell**: `bash` (sandboxed), plus persistent variants
- **Web**: `web_search` (DeepSeek search) and `web_fetch` (HTTP fetch with SSRF-safe destination validation)
- **Session**: JSONL persistence, checkpointing, compaction, token metering, resume
- **Structure**: `todo_write`, goals, plan mode, skills, jobs, subagents, workflow scripts, `ask_user_question`
- **Provider abstraction**: DeepSeek official plus a `pi-ai` multi-provider adapter

Not present in `dsh-base` / `dsh-sdk-app`: the MCP client
(`@deepseek-ai/dsh-mcp-client` is shipped only in the top-level `dsh` package
closure, not in the SDK bundle's dependency tree). It must be added to the
profile explicitly.

### Distribution and integration surface

`pip install deepseek-harness-sdk` also installs
`deepseek-harness-runtime-bin`, a **platform wheel containing a self-contained
`dsh` executable** — so no system Node.js is needed at runtime. Published
targets: Linux x64/arm64, macOS arm64/x64, Windows x64. Wheels are 72–80 MB
compressed (~267 MB installed).

The SDK is a synchronous JSON-RPC-over-stdio client:

```python
from deepseek_harness import DeepSeekHarness

with DeepSeekHarness(
    dsh_home="/var/lib/llm-researcher/dsh",   # explicit, never defaults to ~/.dsh
    cwd="/workspace/research",                # agent workspace
    runtime_cwd="/opt/dsh-runtime",           # subprocess cwd (see §7.2)
    provider="deepseek-official",
    model="deepseek-flash",
    reasoning_effort="high",
    max_tokens=49_152,
    env={"DSH_TELEMETRY_DISABLED": "1"},
) as harness:
    result = harness.run("...", session_id="research-42",
                         on_notification=forward_to_websocket)
```

`on_notification` receives every `session.event` / `session.status` /
`subagent.*` frame as it happens — a direct feed for the existing WebSocket
progress channel. `start_session(session_id=...)` continues a durable
conversation, which maps onto research resume.

### Hard limits that matter here (from DSH's own docs)

1. **No structured output.** No JSON-schema response format in `dsh-llm`.
   The repo's `JsonOutputParser`-based node contracts (planner → sub-queries,
   synthesis → sections) have no direct equivalent; it becomes prompt-and-parse.
2. **No per-prompt cancellation and no per-prompt result.** The wire has no
   cancel method and SDK-created agents stay live until process shutdown.
   `Session.run()` owns an activity interval ending at whole-agent idle.
3. **Approval fails closed.** Base composition pins a `workspace-write` sandbox
   with `approval: ask`, and the approval policy only becomes `never` when
   `DSH_PERMISSION_MODE=danger-full-access`.
4. **Pre-release.** `0.1.5-rc.x`; the CLI at 0.1.5-rc.3 and the pip SDK at
   0.1.5rc1. `requirements.txt` currently pins exact versions, so this adds a
   fast-moving native dependency to a self-hostable product.

---

## 5. Option space

### Option A — Harness owns the run (process-level delegation)

`POST /research` starts a DSH session with a research persona; the model calls
research tools; the API tails `session.event` into the WebSocket and persists
results.

- **Deleted**: orchestrator, LangGraph graph, LLM provider layer, intent router,
  query expander, most of `research_service`.
- **Must be built**: the domain tools as MCP tools; KB-write tools that enforce
  dedupe/merge (because LangGraph's `merge_lists`/`merge_dicts` reducers
  disappear — see §6); a process-per-run lifecycle for cancellation.
- **Risk**: highest. Research quality becomes a function of the model's
  tool-choice, and the deterministic plan → search → chase → hypothesize →
  synthesize contract is lost.

### Option B — Harness as a capability seam (recommended first step)

Keep the pipeline. Replace only the acquisition steps that DSH does strictly
better: `web_search`, `web_scrape`, and URL→PDF retrieval. Expose them as a
small `AcquisitionBackend` interface with two implementations (current Python
plugins; DSH harness call) behind the existing `SearchPlugin` protocol.

- **Deleted**: `web_scraper.py`, `web_search.py`, `wikipedia.py`, most of
  `pdf_download.py` (~740 LOC).
- **Preserved**: every research-specific module, the graph, the KB, the frontend.
- **Why first**: it is reversible, testable against the existing suite, and it
  exercises the real integration friction (`.env`, sandbox, credentials,
  streaming) at small blast radius.

### Option C — Harness as a library of the app (the natural end state)

Extract `app/tools/` + `app/nlp/` into a **standalone MCP server** exposing
`search_arxiv`, `search_crossref`, `fetch_and_parse_pdf`, `chase_references`,
`add_source`, `add_finding`, `add_note`, `bibtex_*`. Then the FastAPI app drives
a DSH session whose roster is exactly those tools — the harness supplies
loop/planning/compaction/file-IO, the project supplies research capability.

- This is the architecture where "DSH as a dependency" genuinely pays off, and
  it also makes the domain tools reusable from any MCP client regardless of DSH.
- It requires resolving the MCP-installation blocker (§7.1) and the
  structured-merge blocker (§7.3).

---

## 6. The subtle blocker: state merge semantics

`ResearchState` uses LangGraph reducers:
`Annotated[list, merge_lists]` / `Annotated[dict, merge_dicts]`
(`app/memory/research_state.py:149-248`), and nodes return partial dicts that
LangGraph merges. A harness has no such reducer contract.

If the harness runs the loop, **dedupe and merge must move from the framework
into explicit tools** — `add_source(source)` must dedupe by DOI/URL, `add_finding`
by content key, and so on. This is not a blocker to feasibility, and it happens
to align with the direction already proposed in
[WORKFLOW.md](WORKFLOW.md) (operations on a knowledge base, merge never reset).
But it must be designed, not assumed.

Note also that checkpointing today is **manual**, not LangGraph-native:
`research_service.save_intermediate_state` writes `Research.state_json` on every
node, `orchestrator.py:172` compiles the graph with **no checkpointer**, and
`langgraph-checkpoint-postgres` is a declared but unused dependency. Resume is
`ResearchState.from_dict` + `determine_resume_point`. So this machinery is
already hand-rolled and could be re-pointed at session persistence — but it is
also not the "framework magic" that a harness would be replacing.

---

## 7. Blockers and gotchas (verified, not hypothetical)

### 7.1 MCP tools need a profile step (medium)

`dsh-mcp-client` is **not** in the SDK profile's dependency tree. Adding it
requires `dsh plugin --profile sdk add ...`, which needs **pnpm** and network at
build time. For a Docker deployment that means baking a prepared `DSH_HOME`
profile into the image. Feasible; a real build-pipeline task.

### 7.2 DSH refuses to boot in this repo as-is (low effort, high surprise)

Running `dsh` from the project root fails immediately:

```
Error: dsh: .env sets "DEEPSEEK_BASE_URL", which only the launching environment may set
```

DSH reads layered `.env` files and **rejects** launcher-owned variables set
there. Mitigation: give the harness a dedicated `runtime_cwd` (and `dsh_home`)
outside the repo, and pass credentials through `HarnessConfig.api_key` /
`base_url` / `env`. Do not let the agent workspace be the project root.

### 7.3 No structured output (medium)

See §4. The pipeline's JSON-parsed node outputs need prompt-and-parse or
tool-mediated structured writes. Related: the harness fixes a *coding-agent*
persona prefix by default (`You are a coding agent powered by the {{model}}
model.`), which must be overridden via a custom `system-prompt` row in the
profile patch — otherwise research prompts carry coding-agent framing.

### 7.4 Cancellation cannot cross the process boundary (medium)

`asyncio.Task.cancel()` and the `cancelled_research_ids` set give per-research
cancel today. DSH's wire has no prompt-cancel and no per-session close. Choose
one: one runtime process per research run (kill = cancel), or accept
cancellation-at-idle-granularity via a client-side activity interval.

### 7.5 Image size and platform matrix (low-medium)

+72–80 MB compressed per platform (~267 MB installed) on top of an image that
already carries pandoc + TeX Live. Published wheels cover the realistic targets
(Linux x64/arm64, macOS both, Windows x64); note the macOS wheels are tagged
`macosx_14_0` and there is **no Windows arm64** wheel. This is an acceptable
cost for a self-hosted tool but should be a conscious one.

### 7.6 Supply chain and version churn (medium)

A pre-release native binary becomes a runtime dependency of a beta product
whose `.env.example` already pins a DeepSeek model id (now `deepseek-flash`,
which the upstream release replaced once already). Pin the SDK and runtime
to exact versions, and decide the supported-platform policy explicitly.

### 7.7 Telemetry default (low, but check it)

DSH's OTel row defaults to `FEEDBACK_ONLY` (releases only on explicit user
feedback). Set `DSH_TELEMETRY_DISABLED=1` for a self-hosted deployment and
document it in `SECURITY.md`/`README.md`.

---

## 8. Independent critique of the current design

Findings below are from reading the code, not from the DSH comparison. They are
ordered by severity, and the first four **change the recommendation**.

### 8.1 Resume silently destroys the knowledge base — including user data (critical)

`process_research_async` deletes every source, finding, and note for the research
before re-running the workflow (`app/services/research_service.py:196-209`):

```python
db.query(models.ResearchSource).filter(...).delete(...)
db.query(models.ResearchFinding).filter(...).delete(...)
db.query(models.ResearchNote).filter(...).delete(...)
db.commit()
```

Notes carry `agent="user"` (`app/services/chat_handlers.py:265,273,430,458,591`),
sources carry user `user_notes` and `tags` (editable per
`app/routers/sources.py:146`), and note/finding rows are editable over the API.
So `POST /research/{id}/resume`:

1. deletes user-authored notes, tags, and source annotations;
2. deletes the KB the pipeline had already built;
3. re-runs **from `pending` status only** (see the repair in `tasks.md`), and if
   the resumed run fails partway — likely, since the first run is what errored —
   the KB is gone with nothing regenerated.

This directly contradicts the product's headline claim: "a **persistent knowledge
base** … you can explore, edit, and refine across sessions" (README.md:10-11).
It is rows in the *ground truth* store being deleted by an *execution* control.

### 8.2 The report is written from search snippets, not from papers (critical)

`pdf_parser.py` (492 LOC, GROBID TEI + pdfplumber/PyPDF2 fallbacks),
`document_chunker.py` (466 LOC) and `pdf_download.py` (347 LOC) have **no
production consumer** — `grep -rn "document_chunker|pdf_parser|chunk_text|
parse_pdf" app/` outside `app/tools/` returns nothing. Synthesis builds its entire
context from `citation.snippet[:excerpt_chars]` with a default of **1200
characters per source** (`app/agents/synthesis_agent.py:62-75`,
`config.py` `research_synthesis_excerpt_chars`).

Unpaywall-era papers are 6,000–12,000 words. A 1,200-character abstract +
search-result blurb cannot support claim-level attribution, numeric results,
method comparison, or limitations — which is precisely what "academic research
assistant" promises. The single highest-leverage improvement available to this
project is wiring fetched full text through the chunker into synthesis with
attribution, and that work is already 90% written and unit-tested. It is not
done, so the ceiling on research quality is set by the snippet length.

### 8.3 Citation persistence has no dedupe; findings bind by dictionary order

`save_citations_to_db` inserts a row per citation with no uniqueness check on
`url` or DOI (`app/services/research_service.py:29-47`). The reference chaser
re-queries the same literature across sub-queries and relaxations, so
re-discovered papers become duplicate rows. `save_findings_to_db` then builds
`url_to_source_id = {s.url: s.id for s in sources}` (`:75-78`) — a plain dict, so
when a URL repeats, **last-write-wins** decides which source id a finding's
evidence points at. Evidence links are therefore order-dependent and can point at
a duplicate row rather than the canonical source.

### 8.4 There is no claim-level provenance in the data model

`ResearchFinding` and `ResearchNote` have no confidence, no evidence span, no
verification state, and no claim↔source binding beyond a list of source ids. The
KB stores *documents*, not *assertions*. Milestone 3 wants claim verification,
credibility scoring, and provenance (ROADMAP.md:103-112) — none of it has a place
to live. Adding an evidence/claim table is a schema decision that should precede
any harness work, because it determines what tools the harness would expose.

### 8.5 The worker serializes the pipeline, so the concurrency machinery is moot

`background_task_worker` `await`s `asyncio.to_thread(process_research, ...)`
inside its polling loop (`app/main.py:59-63`), so exactly one research run
executes at a time and the loop stops polling until it finishes. Meanwhile
`research_service` already implements a safe atomic claim
(`UPDATE … WHERE status='pending'`), `llm_max_concurrent_requests` (default 2)
and a global LLM semaphore exist to bound *concurrent* runs — which can never
happen. The claim path is built for a concurrency that the scheduler prevents.

### 8.6 Pre-existing event-loop bugs (masked by 8.5)

- `_llm_semaphore` is a process-global `asyncio.Semaphore` created lazily
  (`app/llm_provider.py:16-27`). Every research run gets a **new event loop**
  (`asyncio.run` at `research_service.py:319`, invoked from a worker thread).
  A semaphore bound to loop A, acquired from loop B, is exactly the
  cross-loop failure class. Today the serialized worker hides it; the moment two
  concurrent runs exist, it surfaces.
- `websocket_manager.ConnectionManager._lock` (`:23`) and the module-scoped locks
  in `openalex_search.py:30` / `semantic_scholar.py:35` have the same shape. Runs
  broadcast over `ws_manager` from their worker-thread event loop
  (`research_service.py:139,176,215,252,282,296`) while connections are
  registered from the server's main loop (`routers/chat.py:150`) — two loops
  touching one in-memory object.

The correct home for cross-run back-pressure is the database (or a real queue),
and the correct home for progress fanout is a loop-agnostic channel. Neither
needs DSH.

### 8.7 LangGraph earns almost nothing here

`orchestrator.py:172` compiles the graph with **no checkpointer**;
`langgraph-checkpoint-postgres` is declared in `requirements.txt` and imported
nowhere; `research_state.py:163`'s docstring claims PostgreSQL checkpointing that
does not exist. The graph is six nodes in a chain with two error exit edges and
**no state-driven branching** — `should_continue_after_search` is effectively
"did search produce anything". Resume is a hand-written field heuristic
(`determine_resume_point`, `orchestrator.py:89-104`) feeding a dynamic
`set_entry_point`.

That is a `for` loop with extra dependencies. Either commit to the framework
(checkpointer, real conditional edges, durable human-in-the-loop interrupts) or
delete it. The current middle position costs a dependency, a 291-line driver, and
a misleading docstring while delivering none of LangGraph's value.

### 8.8 The AI-state UI is coupled to a design the roadmap intends to remove

`GET /research/{id}/state` and `/steps` (`routers/state.py:42-120`) expose raw
pipeline internals, consumed by `StateInspector` / `ResearchPlanTab` /
`TimelineView` / `AgentSteps` (frontend `api/client.ts:214,252`). Milestone 2
replaces the pipeline with composable operations, and Milestone 3 adds
verification — at which point "the AI's internal stage state" is the wrong thing
to show a researcher. It should show **evidence, claims, and their sources**. The
frontend has an investment here that a harness migration would strand, and so
would a correct Milestone 2/3 implementation. Worth deciding deliberately rather
than inheriting.

### 8.9 The test suite cannot detect a research-quality regression

13 test files, ~6,600 LOC, LLM mocked throughout, no evaluation set, no golden
research output, no faithfulness metric (`grep -riE "eval|grounding|faithful|
hallucinat" tests/` → only incidental word matches). The suite proves the plumbing
works; it says nothing about whether the output is *correct*. This is the
structural reason all of the above went unnoticed, and it is why "swap the runtime
and see" is not a safe experiment: there is no instrument to read.

---

## 9. Revised recommendation

The critique above reorders the work. The agent runtime was never the bottleneck.

**Phase 0 — fix the data-integrity bugs. Nothing else first.**

1. Make resume **non-destructive**: stop deleting rows; make saves idempotent by
   URL/DOI (`INSERT … ON CONFLICT` / get-or-create), and never delete rows with
   `agent="user"` or user `tags`/`user_notes`. Treat the KB as the durable record
   and `state_json` as disposable execution context.
2. Add a unique constraint on `(research_id, url)` (or a normalized DOI key) and
   fix `url_to_source_id` to be conflict-free.
3. Decide the event-loop strategy: fail-fast DB-backed concurrency control, and
   progress fanout that does not depend on a loop-bound in-memory lock.

**Phase 1 — fix the evidence model, which is the actual product.**

4. Wire `pdf_download` → `pdf_parser` → `document_chunker` into the search and
   synthesis path (and fix the swapped `get_setting` arguments at
   `pdf_download.py:55,63`, `pdf_parser.py:93` that currently break the cache dir
   and GROBID URL). This alone should move output quality more than any runtime
   change.
5. Add claim/evidence records with spans, confidence, and verification state, and
   surface those in the UI instead of raw pipeline state.
6. Register the four orphaned academic plugins (PubMed, Crossref, OpenAlex,
   Semantic Scholar) or delete them — shipping unused tested code inflates
   apparent capability.

**Phase 2 — build the evaluation set before any runtime comparison.**

7. ~30 questions with expected evidence; measure citation precision, claim
   support, and source recall. Without this, no architectural change is
   verifiable.

**Phase 3 — then the harness question, on evidence.**

8. Pilot DSH for acquisition (Option B), and only pursue process-level
   delegation (Option C) if it beats the pipeline on the Phase 2 metrics.

**Explicit non-recommendations**: don't rewrite `app/agents/*` as harness
subagents first; don't delete the LangGraph layer until its replacement exists
and is measured; don't treat "fewer lines of code" as the success metric for a
project whose problem is research quality, not code volume.

---

## 10. Original recommendation (superseded by §9, kept for reference)

**Do not replace the infrastructure now. Do adopt the seam.**

1. **Phase 0 (cheap, independent of DSH).** Fix the concrete defects found while
   inventorying, because they limit any later comparison:
   - `get_setting(value, setting_name)` is called with the arguments swapped at
     `app/tools/pdf_download.py:55,63` and `app/tools/pdf_parser.py:93`, so the
     PDF cache dir and GROBID server resolve to literal strings and
     `MAX_PDF_SIZE_MB` silently falls back to 50 MB.
   - `pubmed_search`, `crossref_search`, `openalex_search`, `semantic_scholar`
     are implemented, tested, exported — and **never registered**
     (`plugins.py:177-181` registers only web/arxiv/wikipedia/springer/elsevier).
   - `pdf_parser`, `document_chunker`, `pdf_download` have no production
     consumer, yet ROADMAP Milestone 3 wants PDF grounding wired in.
   - Drop the unused `langgraph-checkpoint-postgres` dependency or fix the
     docstring claiming checkpointing exists.

2. **Phase 1 — pilot the acquisition seam (Option B).** Add a
   `HarnessClient` wrapper, route `web_search` / `web_scrape` / PDF retrieval
   through DSH behind the existing plugin protocol, and run the current test
   suite plus one end-to-end query with both backends. Success criteria: equal
   or better source yield, equal citation quality, and no `.env`/sandbox/
   approval surprises in a container.

3. **Phase 2 — extract the domain tools as an MCP server.** Independent of
   DSH and valuable on its own: it decouples `app/tools/` from this app,
   makes the research plugins reusable and separately testable, and is the
   prerequisite for Option C.

4. **Phase 3 — decide with evidence.** Build the small evaluation set that
   ROADMAP Milestone 3 already asks for, and compare a harness-driven run
   against the pipeline on *research quality* (grounded claims, citation
   correctness, source recall) — not on LOC deleted. Revisit Option C only if
   the harness wins on quality, and only after the DSH runtime leaves rc.

**Explicit non-recommendation**: do not rewrite `app/agents/*` (2,200 LOC of
prompts and pipeline logic) as harness subagents as a first move. That code is
the product's current quality baseline; replacing it with model-driven tool
choice before there is an evaluation set means losing the ability to tell
whether quality went up or down.

---

## 11. Answers to the original questions

- **Is most of the code base redundant given DSH?** No. ~13% (≈2,700 of 21,000
  backend LOC) is generic plumbing DSH duplicates, plus ~740 LOC of web
  acquisition DSH does better. The ~8,000 LOC of domain research capability is
  not something a general harness provides.
- **Is it feasible to add DSH as a dependency?** Yes, and cleanly: an official
  Python SDK exists, the SDK bundles its own runtime so no system Node.js is
  required, the domain tools have zero LangChain coupling and already match the
  MCP tool shape, and DSH's notification stream maps onto the existing
  WebSocket progress channel.
- **Should it be done now?** Not as a replacement. The integration friction
  (pre-release runtime, no structured output, no prompt cancellation,
  MCP-in-profile build step, approval policy, `.env` rejection, +80 MB per
  platform) is real, and the payoff is deleting the layer that already works
  while leaving the layer that creates value — Milestone 2's open workflow and
  Milestone 3's verification/credibility work — still unbuilt.
