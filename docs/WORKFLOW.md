# LLM Researcher — Open Research Workflow (Design Proposal)

**Last updated**: 2026-08-10
**Status**: Proposal — pending review

## 1. Motivation

Today the system is **pipeline-oriented**: creating a research item fires one
monolithic workflow (`plan → search → chase references → hypothesize →
synthesize → format`) that runs to completion and overwrites the research
state.

Real research is not a pipeline. Researchers work iteratively:

1. Create a research item / topic.
2. Add notes and references by hand.
3. Ask the assistant to find *more* references.
4. Ask the assistant to fact-check claims.
5. Add more notes.
6. Finally — only when the knowledge base is mature — ask for a report.

This proposal makes that open, iterative loop the **primary interaction
model**, and demotes the monolithic pipeline to an optional "autonomous fast
path".

## 2. Current Interaction Model

### What already exists

The chat layer (`app/agents/intent_router.py` +
`app/services/chat_handlers.py`) already implements most of the open workflow
as intents:

| Intent | Operation | Status |
|---|---|---|
| `research` | Run full pipeline on a topic | ✅ but always end-to-end |
| `question` | Q&A over the knowledge base | ✅ |
| `add` | Add a URL (scraped) or a note | ✅ |
| `remove` | Remove a source | ✅ |
| `edit` | Edit notes / tags / source notes | ✅ |
| `browse` | List / filter the knowledge base | ✅ |
| `status` | Show research state | ✅ |
| `generate` | Generate/regenerate report from current KB | ✅ `handle_generate_intent` |

### The gaps

| Missing capability | Impact |
|---|---|
| **Find more sources** (search & merge, no synthesis) | "Look for more references" always triggers the full pipeline; new results are not merged into the existing KB. |
| **Fact-checking** | Does not exist at all. |
| **Incremental execution** | Pipeline phases cannot run individually; state is overwritten rather than merged. |
| **KB-shaped state** | `ResearchState` is pipeline-shaped (sub_queries → citations → draft); no record of open questions, gaps, or verification status. |

## 3. Proposed Model: Operations on a Knowledge Base

### Mental model

- The **knowledge base is the record of truth** (sources, findings, notes).
- The **workflow is a set of composable operations** the user triggers on
  demand.
- The **monolithic pipeline is one operation** ("autonomous research") among
  many.

### Operation catalog

| Operation | Trigger | Inputs | Behavior | Status |
|---|---|---|---|---|
| `create_research` | UI / API | topic | Create an (empty) research item | ✅ exists |
| `add_note` | chat / UI | content | Save note (agent = user) | ✅ exists |
| `add_source` | chat / UI | URL | Scrape & save source | ✅ exists |
| `remove_source` / `edit_*` | chat / UI | identifiers | Mutate the KB | ✅ exists |
| `find_sources` | chat / UI | topic or "fill gaps" | Search plugins, **merge** sources into KB, stop | 🆕 extract from pipeline |
| `chase_references` | chat / UI | — | Follow citations from KB sources, merge | 🆕 extract from pipeline |
| `fact_check` | chat / UI | scope (notes / draft) | Verify claims against KB sources; write verification note | 🆕 new |
| `synthesize` | chat / UI | instructions | Generate/regenerate report from current KB | ✅ exists → promote |
| `autonomous_research` | UI button | topic | Full pipeline (fast path) | ✅ exists (rename) |

### Example session

```
1. "Create a research item: CRISPR delivery systems"   → item created
2. "Add note: compare lipid nanoparticles vs viral vectors"
3. "Add https://doi.org/..."                           → source scraped & saved
4. "Find more sources about exosome-based delivery"    → find_sources merges 5 new sources
5. "Fact-check my notes"                               → verification note written
6. "Add note: NN-based delivery has low in-vivo stability"
7. "Generate a report draft"                           → synthesize from KB + notes

## 4. UI Surfacing

Chat alone is not enough — operations must be visible:

- **Research detail action bar**: "Find sources", "Chase references",
  "Fact-check", "Generate report", "Full research".
- Each operation streams progress over the existing WebSocket channel.
- A **"Verification" tab** shows per-claim status (verified / unsupported /
  contradicted) with source links (follow-on from `fact_check`).
- Keep the existing **"New Research"** button as the *autonomous fast path*.

## 5. State Model Implications

Additions to `ResearchState` (all **additive / backward compatible**):

- `open_questions: list[str]` — surfaced by planner / `find_sources` /
  `fact_check`
- `gaps: list[str]` — topics the KB is missing
- `verification: list[VerificationClaim]` — claim, verdict, supporting
  source IDs

These make the KB queryable and give the planner / fact-checker context.

## 6. Evolution Plan

> Tracked in [ROADMAP.md](ROADMAP.md) — Milestone 2.

### Step 1 — Extract search & reference-chasing into standalone operations
- Refactor `app/agents/search_agent.py` + `app/agents/reference_chaser.py`
  calls out of the orchestrator into a `collect_sources(research_id, query,
  chase=True)` service that **merges** citations into the KB (dedupe by URL)
  and stops.
- Add chat intent + UI button ("Find more sources").
- **Effort**: S–M.

### Step 2 — Fact-checking operation
- New `verify_claims(scope)` service: LLM extracts claims from notes/draft and
  checks each against KB source snippets; writes a `ResearchNote` with
  per-claim verdicts (verified / unsupported / contradicted / needs review).
- New `fact_check` intent + UI button.
- **Effort**: M.

### Step 3 — Incremental, invokable phases
- Make every pipeline phase individually callable from `process_research` and
  always **merge** instead of resetting state.
- Rename the full run to "autonomous mode" and keep it one click away.
- **Effort**: M.

### Step 4 — KB-shaped state + verification UI
- Add `open_questions`, `gaps`, `verification` to `ResearchState`; surface
  them in a new "Verification" tab.
- **Effort**: M–L.

## 7. Trade-offs & Risks

- **Intent reliability**: the open model depends on intent classification;
  wrong routing = wrong operation. Mitigations: explicit UI buttons, cheap
  heuristics for unambiguous patterns, confirm-before-execute for destructive
  ops.
- **Discoverability**: users won't use invisible operations → explicit action
  bar and suggested next steps after each operation (the chat layer already
  returns `suggestions`).
- **Fact-checking is approximate**: LLM verification over snippets is a
  *triage tool for human review*, never a claim of ground truth. The UI/doc
  must say so.
- **Don't lose the fast path**: autonomous mode remains valuable; keep it
  prominent.

## 8. Open Questions

- Should `find_sources` take an explicit topic or derive it from
  `open_questions` / `gaps`? (Proposal: both — explicit topic wins,
  otherwise gaps.)
- Should fact-check annotate the draft inline or write standalone notes?
  (Proposal: standalone notes with claim IDs; inline annotation later.)
- Should the report be editable in-app and re-synthesized in place?
- Does "full research" stay a single state, or become a scripted sequence of
  the above operations? (Proposal: scripted sequence — less special-casing.)

```
