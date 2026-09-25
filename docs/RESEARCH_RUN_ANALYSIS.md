# Run analysis — "functional programming in web development in 2026"

**Run date**: 2026-09-25 · **Research item**: `id=1` · **Status**: `complete`
**Mode**: live API (`scripts/dev_server.py`, in-memory SQLite, real DeepSeek + Tavily + arXiv/Wikipedia)
**Artifacts**: [`smoke_artifacts/fp2026/`](../smoke_artifacts/fp2026/) (full dump of every read endpoint + exports)
**Capture script**: [`scripts/capture_fp2026.py`](../scripts/capture_fp2026.py)

This document is a post-mortem of one real end-to-end run, written to turn
observed behaviour into concrete, prioritized changes. Everything below is
backed by a log line, an API response, or a persisted row captured in the
artifact directory.

---

## Status — P0 fixes implemented and verified (2026-09-25)

All four P0 items below are fixed, unit-tested, and re-verified with a live
end-to-end run on the same query. Evidence: [`smoke_artifacts/fp2026_verified/`](../smoke_artifacts/fp2026_verified/)
and `scripts/verify_run.py`.

| P0 | Change | Where |
|---|---|---|
| **P0-1** citation numbering | Number cited sources `1..N` once, after collection; rewrite inline markers + reference list; persist the number per source and return it from the API | `app/services/citation_numbering.py`, `app/services/research_service.py`, `research_sources.citation_marker` (+ Alembic `b3c91d4f7a20`), `app/schemas.py` |
| **P0-2** over-strict relevance filter | Recall-oriented prompt; skipped/failed assessments keep their source; a sub-query that would be emptied keeps its best few | `app/agents/search_agent.py`, `RESEARCH_RELEVANCE_*` settings |
| **P0-3** one LLM call per citation | Batched assessment (20 sources per call) | `app/agents/search_agent.py` |
| **P0-4** arXiv always failing | `all:`-prefixed sanitized queries, exactly one request per call, process-wide 3 s pacing, rate-limit cooldown, first-variation only, planner's academic flag finally consumed | `app/tools/arxiv_search.py`, `app/tools/plugins.py`, `app/agents/search_agent.py`, `ARXIV_*` settings |

### Measured effect (same query, same provider, same machine)

| Metric | Before | After |
|---|---|---|
| Search phase | 226 s | **120 s** (−47 %) |
| End-to-end | 371 s | **306 s** (−18 %) |
| Sources persisted | 16 | **36** |
| Findings (sub-questions with sources) | 3 / 5 | **5 / 5** |
| Sub-queries left with 0 sources | 2 / 5 | **0 / 5** |
| Relevance calls in the search phase | 76 | **5** |
| Reference list | `1–11, 14–18` (gaps) | **`1–30`, contiguous** |
| Markers resolvable to a source row | 0 / 16 | **30 / 30** |
| arXiv sources | 0 (all calls 406) | 0 — see caveat |

`scripts/verify_run.py` reports `ALL CHECKS PASSED` on the verified run.

**arXiv caveat.** The client-side defects are fixed and arXiv's query API is
reached correctly, but this machine's IP was still being throttled
(`HTTP 406`) during the verification run, so no arXiv source was collected.
The same sanitized query returns `200` and one result when issued after a quiet
period, which is why the tool now paces, issues one request per call, and backs
off for `ARXIV_RATE_LIMIT_COOLDOWN_SECONDS` instead of retrying into the
throttle. Expect arXiv to contribute on a deployment that has not been making
ad-hoc requests to it; `scripts/verify_run.py` prints the contributing source
types so this stays visible.

---

## 1. What was run

```bash
.venv/bin/python scripts/dev_server.py --port 8000          # live API
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"query": "functional programming in web development in 2026"}'
.venv/bin/python scripts/capture_fp2026.py 1 smoke_artifacts/fp2026
```

### Timeline (server clock, from `/steps`, `/research/{id}`, server log)

| Time | Phase | Duration | What happened |
|---|---|---|---|
| 19:03:25 | **plan** | ~3 s | planner → 5 sub-questions, `include_academic=true` |
| 19:03:28 | **search** | **3 m 43 s** | 5 sub-queries × 3 query variations; **76 per-citation relevance LLM calls**; arXiv and Wikipedia failed |
| 19:07:11 | **chase_references** | 24 s | 10 → 13 citations |
| 19:07:35 | **hypothesize** | 1 m 33 s | 4 hypotheses; 2 "could not find evidence"; 13 → 18 citations |
| 19:09:08 | **synthesize** | 28 s | 17 483-char draft from 18 sources |
| 19:09:36 | **format** | <1 s | 16 cited refs kept, 2 uncited filtered |
| **19:09:36** | **complete** | **6 m 11 s total** | 20 219-char document, 16 sources, 3 findings |

Roughly **~100 LLM calls** for one report, serialized 2-at-a-time by
`llm_max_concurrent_requests: int = 2` (`app/config.py:84`).

### Output produced

| Artifact | Result |
|---|---|
| Document | 2 481-word body (target 2 500 — 99 %), structured as intro + one section per sub-question + cross-cutting analysis + conclusion, with inline `[n]` citations |
| Sources | 16 (all `source_type=web`) |
| Findings | 3 (for 5 sub-questions) |
| Knowledge base | 5 sub-queries, 3 with sources, 2 empty |
| Exports | Markdown 200 ✅, BibTeX 200 ✅, findings CSV/JSON 200 ✅, data JSON 200 ✅, **HTML/PDF/DOCX 503** (no pandoc) |
| Full-text evidence | **0 passages** — grounding never engaged |
| `/plan` progress | `completed: 0 / pending: 5` **even though the run finished** |
| `/state` | returns an 8-key summary, not the LangGraph state the docs promise |

---

## 2. What the output gets right

Worth stating before the defect list — this run is not a failure:

- **Planning is genuinely good.** The 5 sub-questions are non-overlapping and
  cover definition → landscape → patterns → barriers → outlook, exactly the
  decomposition a human would write.
- **The report structure is sound.** Every one of the 5 planned sub-questions
  has its own section, plus a cross-cutting analysis and conclusion; the word
  target is hit; the prose synthesizes across sources instead of summarizing
  them one by one.
- **Numbers in the text are traceable to snippets.** Spot-checks hold up:
  "~200K downloads/week" is verbatim in the snippet persisted for source id 13;
  the "7 percentage-point increase from 2024 to 2025" is verbatim in source id
  11. The synthesis prompt's anti-hallucination rules are working.
- **The model's own "what's missing" pass is honest.** The hypothesis agent
  explicitly recorded "Current findings are mostly introductory articles,
  listicles, and duplicate glossary content" and flagged two hypotheses it
  could not evidence.
- **The pipeline degrades gracefully.** arXiv failed on every call, Wikipedia
  raised, two sub-queries returned zero sources — and the run still completed
  with a usable document rather than failing.

---

## 3. Defects found, prioritized

### P0-1 — Report citation numbers do not match API/DB source IDs ✅ FIXED

**Evidence.** The report's reference list uses markers `[1]…[11], [14]…[18]`;
`GET /research/1/sources` returns ids `1…16`. Resolving each reference URL
against the sources table:

```
report [14] -> DB source 12    report [16] -> DB source 14    report [18] -> DB source 16
report [15] -> DB source 13    report [17] -> DB source 15
```

Every citation from `[14]` onward is **off by two**, and two markers (`[12]`,
`[13]`) exist in the body's numbering gap with no reference entry at all. A
reader (or the frontend, or another agent) who follows citation `[16]` lands on
a *different source* than the one the sentence was written from.

**Root cause.** Two numbering systems are never reconciled:

1. `app/agents/search_agent.py` assigns sequential markers during collection
   (`citation.id = f"[{len(unique)+1}]"`), and later agents continue the
   sequence (`reference_chaser.py:547`, `hypothesis_agent.py:564`).
2. `app/services/research_service.py::save_citations_to_db` writes rows whose
   primary key is assigned by the **merge order and identity dedup**, which
   differs from the marker sequence whenever two citations merge by
   `source_identity`. Here the two uncited citations (step metadata
   `skipped_titles`) are both titled *"Functional Programming: Principles and
   Practices"* — the same title as DB row `[4]` — i.e. duplicate discoveries of
   one article under two URL spellings; the merge collapsed 18 state citations
   into 16 rows and shifted every later row id down by two.
3. `app/agents/synthesis_agent.py:361-406` filters out uncited citations but
   keeps their original sparse markers, so the reference list also keeps the
   resulting gaps.

**Suggested fix.** Number sources once, in the knowledge base, and make the
document use those numbers: after `save_citations_to_db` returns the identity
map, persist the marker on `ResearchSource` (e.g. `citation_marker`), then have
`format_final_document` renumber cited citations `1..N` **and rewrite the
inline markers in the draft** to match. At minimum, renumber contiguously so
the reference list has no holes.

---

### P0-2 — The relevance filter throws away the best sources ✅ FIXED

**Evidence** (server log, this run):

```
[RELEVANCE] Kept 5/14 citations after filtering     # "core principles and benefits"
[RELEVANCE] Kept 2/17 citations after filtering     # "most prominent languages/frameworks"
```

Sources **explicitly on topic** were dropped, with reasons like:

- `"Best Functional Programming Languages in 2026"` → filtered, *"does not
  specifically address their prominence in web development"*
- `"Functional Programming Languages: The 2026 Complete Guide"` → filtered
- `"Tarides | What is Functional Programming?"` → filtered
- `"The Functional Programming Paradigm: Concepts, Principles..."` → filtered
  (a paper the report then cites as [3] after the hypothesis phase re-found it)

Two of five sub-questions (`barriers`, `outlook`) ended with **zero** sources
and were only rescued by the hypothesis agent's ad-hoc re-search. Findings
count (3) < sub-question count (5) is the downstream symptom.

**Root cause.** `RELEVANCE_PROMPT` (`app/agents/search_agent.py:42-66`) tells
the model to *"Be strict — when in doubt, mark as irrelevant"*, and judges
against the **entire multi-clause sub-question** using only
`citation.snippet[:500]` (`search_agent.py:98`). Tavily snippets frequently
begin with navigation boilerplate, so the model correctly observes *"the
snippet only contains navigation/menu text"* and rejects. It is being asked a
precision question where the pipeline needs recall.

**Suggested fix.** (a) Reframe the prompt around *"would this source contain
useful evidence for any part of this sub-question?"* and drop the "when in
doubt reject" instruction; (b) judge against the **main query + sub-query**,
not the sub-query's every clause; (c) strip nav boilerplate before assessment
(see P1-3); (d) keep a cheap lexical/title fallback so a sub-query can never
end up with zero sources.

---

### P0-3 — Runtime is dominated by one LLM call per citation ✅ FIXED

**Evidence.** 76 relevance assessments (14+17+15+13+17) at concurrency 2
account for the bulk of the 3 m 43 s search phase — ~61 % of the whole run.

**Root cause.** `filter_relevant_citations` fans out one LLM call per citation
(`search_agent.py:139-144`), throttled globally to 2 concurrent requests.

**Suggested fix.** Batch it: the reference chaser already has exactly the right
pattern (`ReferenceBatchRelevance`, `reference_chaser.py:57-99`) that assesses
a list in one call. Reusing a batched schema for citations turns ~76 calls into
~5–8 and should cut end-to-end time substantially with no loss of signal.

---

### P0-4 — The arXiv plugin always fails (HTTP 406) ✅ FIXED (client side)

**Evidence.** Every arXiv call in the log:

```
arxiv.HTTPError: Page request resulted in HTTP 406
https://export.arxiv.org/api/query?search_query=Which+functional+programming+languages%2C+frameworks%2C...
```

The query is the raw natural-language sub-query, commas and question mark
included. `arxiv_search` passes it straight into `arxiv.Search(query=...)`
(`app/tools/arxiv_search.py:57-61`); the API requires field-prefixed syntax
(`all:...`) and rejects this. **Every arXiv request in the log failed with HTTP
406** (shown for two variations of the "languages/frameworks" sub-query), and
**no arXiv source reached the knowledge base**: all 16 persisted sources are
`source_type=web`. Each failure also costs 4 attempts × 3 s sleeps before
giving up.

Two related issues in the same area:

- `is_academic_query` (`app/tools/arxiv_search.py:83-98`) treats *framework*,
  *approach*, *model* and *method* as academic markers, so sub-questions like
  "…languages, **frameworks**, and libraries…" are classified academic while
  genuinely technical ones are not — the gate is noise.
- The planner already returns an `include_academic` flag
  (`app/agents/planner.py:31-34`, `true` for this run), but
  `execute_searches` ignores it and re-derives the decision with the heuristic
  above (`app/agents/search_agent.py:335`). The planner's judgement is
  recorded in step metadata and then thrown away.

**Suggested fix.** Build a proper query (`"all:" + sanitized terms`, quotes
stripped) in `arxiv_search`, and tighten `is_academic_query` so common web
words don't trigger academic plugins.

---

### P1-1 — Wikipedia: one bad page title kills the whole search

**Evidence.**

```
[SEARCH] wikipedia search failed for variation 1:
Page id "open source softwares" does not match any pages. Try another id!
```

`wikipedia_search` loops over `wikipedia.search()` results and calls
`wikipedia.page(title)` / `wikipedia.summary(title)` without a per-title
`try/except` (`app/tools/wikipedia.py:53-66`). One bad suggestion aborts the
loop, so the other 2 valid pages are lost and the entire sub-query's Wikipedia
contribution is marked as an error.

**Suggested fix.** Wrap each page fetch; skip failures; fall back to
`wikipedia.summary(query, auto_suggest=True)` when the exact title misses.

---

### P1-2 — Source metadata is poor, and it leaks into the report and exports

**Evidence** (persisted rows):

- `[8] "Medium"` — the title of a Vlad Antsitovich article is literally the
  site name in the reference list.
- `[11] "2 Technology"` — a Stack Overflow survey anchor page.
- `[2] "The Truth About Functional Programming in 2026 (No One ..."`,
  `[3] "...Concepts, ..."` — truncated titles ending in `...`.
- **No source has an author**, so every reference reads
  `[6] "Top 15 Web Application Languages in 2026 for Businesses." Retrieved from…`
- `GET /export/sources/bibtex` produces:
  `@misc{Unknown2026Medium, abstract = {Sign upSign inSign upSign inUnkno…`

**Root cause.** `WebSearchResult` (`app/tools/web_search.py:21-27`) has no
author and trusts Tavily's `title` verbatim; snippet text is the raw page
intro, which for Medium/Stack Overflow begins with sign-in chrome.

**Suggested fix.** Derive a display title from OpenGraph/`<h1>`/URL slug when
the returned title is a bare site name or ends in `...`; add an
author/domain field to `WebSearchResult`; use the domain as the BibTeX
`author`/`organization` fallback; strip leading boilerplate from snippets.

---

### P1-3 — Boilerplate snippets poison both relevance and synthesis

**Evidence.** Snippets persisted for [1] and [8] begin with
`Sitemap Open in app Sign up Sign in` / `Sign up Sign in Sign up Sign in`.
The relevance model rejected a page with the reason *"The snippet only contains
navigation/menu text, providing no evidence…"*.

**Suggested fix.** Apply the existing `scrape_url` readability path (or a
simple boilerplate prefix trimmer) to the top-K results before relevance
assessment and before writing `content_snippet`; consider Tavily
`include_raw_content` for the most promising hits.

---

### P1-4 — `/plan` progress and `/state` are dead ends

**Evidence.**

- `GET /research/1/plan` after `status=complete` still reports
  `"status": "pending"` for **all 5** sub-queries; `/state` reports
  `"completed": 0, "pending": 5, "completed_queries": []`.
- `app/routers/state.py:289-307` reads `state_data["findings"]`, but nothing in
  `app/agents/**` or `app/services/**` ever writes a `findings` key, and
  `ResearchState` has no such field (`app/memory/research_state.py:180-290`).
  The progress map is therefore **always empty**.
- `GET /research/{id}/state` returns an 8-key summary, while
  `docs/LLM_TESTING.md` and the README advertise it as "full LangGraph state".

**Impact.** The UI plan tab shows no progress during or after a run, and there
is no node-level progress source for agents polling the API. This also hurt
this very analysis: `subq_done=0/5` for the entire 6-minute run.

**Suggested fix.** Populate progress from `sub_query_results` (already in
state) or from persisted findings keyed by sub-query; or return the real
`state_json` from `/state` and derive progress there. Update the docs to match
whichever contract is chosen.

---

### P1-5 — Sources found by the hypothesis phase are attached to no sub-question

**Evidence.** Search yielded 10 sources across sub-queries 1–3 only; reference
chasing added 3; the hypothesis phase added **5** more (all four `pkgpulse.com`
and `tech-insider.org` pages that carry the report's most specific claims about
Effect-TS and Solid/Svelte). `generate_hypotheses` returns
`{"citations": new_citations}` only (`app/agents/hypothesis_agent.py:634-640`)
— no `SubQueryResult` — so those 5 sources appear in no finding and in no
`knowledge_base` group, yet sections 4 and 5 of the report are largely built on
them.

**Impact.** The plan/progress and knowledge base understate what the report
actually relied on; users cannot see why sections 4–5 exist when their
sub-questions have zero sources. It also hides the fact that two sub-questions
were effectively answered by a fallback path.

**Suggested fix.** Attribute hypothesis citations to the sub-query they were
investigating (or a synthetic `hypothesis:<aspect>` result) and persist them as
findings so the KB reflects the real evidence base.

---

### P1-6 — No full-text grounding for non-academic topics

**Evidence.** All 16 sources are `source_type=web`; `research_evidence` is
empty; no `.pdf` URL was ever seen. `is_fulltext_candidate`
(`app/services/fulltext.py:104-126`) only accepts PDF URLs or
`arxiv/openalex/semantic_scholar/pubmed/pdf` source types, and because arXiv
was broken (P0-4) even the academic path produced nothing. The flagship
"quote real paper passages" feature never engaged on a topic where the user
would most want it.

**Suggested fix.** For web sources, fetch the article HTML and use the existing
`web_scraper`/chunker to store passages as evidence (the schema already
supports arbitrary `source_id`); mark `full_text_status="unavailable"` when the
page is unreachable so retries are skipped. Also surface *why* grounding was
empty in `/steps` so users aren't left guessing.

---

### P2-1 — Source diversity is unguarded; SEO pages dominate

**Evidence.** 5 of 16 sources are near-duplicate SEO content:
`pkgpulse.com/guides/effect-ts-vs-fp-ts-2026`,
`pkgpulse.com/blog/effect-ts-vs-fp-ts-functional-typescript-2026`,
`pkgpulse.com/blog/effect-ts-vs-fp-ts-2026`,
`pkgpulse.com/guides/solidjs-vs-svelte-2026`, plus
`tech-insider.org/solidjs-vs-react-vs-svelte-2026`. Three variants of one
article inflate the reference list and the model's confidence (those three are
the most-cited sources in the report: [14]×11, [15]×8, [16]×13).

Dedup exists but is **URL-only in the search agent**
(`search_agent.py:269-274`) and **identity-only in the KB**
(`source_identity`), so different URLs for the same content survive. There is
no per-domain cap and no source-quality signal.

**Suggested fix.** Add a per-domain cap (e.g. ≤3) when assembling the synthesis
source list, and a content-similarity check (title/slug near-duplicate or
snippet shingle overlap) to merge series pages. Longer term this is the
"source credibility scoring" item already in the roadmap.

---

### P2-2 — `research_timeout` is dead configuration; cancellation is coarse

**Evidence.** `grep -rn research_timeout app/` matches only
`app/config.py:35`. Nothing enforces it, and
`process_research_async` checks `cancelled_research_ids` only *before* the
first graph segment and *after* the second
(`app/services/research_service.py:293-302, 396-405`) — a cancel during the
6-minute search phase does nothing until the workflow returns.

**Suggested fix.** Wrap the workflow in `asyncio.wait_for(...)` using
`settings.research_timeout`, and check the cancellation set between graph nodes
(the `on_state_update` callback is already invoked after every node and is the
natural hook).

---

### P2-3 — Known P0/P1 issues reproduced live

- **`tags` / `user_notes` still silently dropped** (`tasks.md` P1): a probe
  request with `tags:["fp","2026"], user_notes:"note-x"` came back
  `"tags": null`, and `PATCH {"user_notes":"note-y","tags":["b"]}` returned
  `user_notes` still `"note-x"`. Confirmed on this build.
- The **chat-intent status trap** (`tasks.md` P0) was not exercised, but the
  same "no status-reset endpoint" gap is what made the probe item require a
  delete.

---

### P2-4 — Smaller inconsistencies worth cleaning up

| Issue | Evidence | Fix |
|---|---|---|
| Search summary contradicts its own steps | Summary step says `"0 errors encountered"` / `total_errors: 0` while two sub-query steps are `status="error"` | Aggregate `SubQueryResult.error` into the count |
| Confusing note text | `Search failed for: <q>. Error: None` (`notes.json`) | Say "no sources found" when `error is None` |
| Meaningless entities | `/entities` returns 2 entities: `"benchmark"` (type `material`) and a 160-char sentence typed `finding` | Fix the extractor or hide the tab until it works (roadmap already flags the NLP module) |
| Exports need pandoc with no hint in the API | `/export/html`, `/export/pdf`, `/export/docx` → `503 {"detail":"... Pandoc is not installed."}` | Return a documented `503` contract (or fall back to Markdown) and note the dependency in the README |
| BibTeX keys are unusable | `@misc{Unknown2026Medium, …}` with nav-text abstracts | See P1-2 |
| Reference list ordering vs API ordering differ | `/sources` returns newest-first (16→1) | Return marker order, or expose the marker explicitly |

---

## 4. Suggested order of work

> Rows 1–3 (all four P0 items) are implemented and verified — see the status
> section at the top. The remaining rows are still open.

| # | Change | Why first | Rough size |
|---|---|---|---|
| 1 | ~~Single source of truth for citation numbering (P0-1)~~ | done | — |
| 2 | ~~Fix arXiv query construction + academic-query heuristic (P0-4)~~ | done (client side; arXiv still throttles this IP) | — |
| 3 | ~~Batch relevance assessment + recall-oriented prompt (P0-2, P0-3)~~ | done — search phase 226 s → 120 s | — |
| 4 | Wikipedia per-page error handling (P1-1) | One-line robustness fix, currently loses whole searches | S |
| 5 | Populate `/plan` progress from `sub_query_results` (P1-4) | Makes runs observable for users and polling agents | S |
| 6 | Snippet/title hygiene (P1-2, P1-3) | Improves relevance decisions and every exported reference | M |
| 7 | Attribute hypothesis citations to sub-queries (P1-5) | KB stops understating the evidence base | M |
| 8 | Web-page evidence for full-text grounding (P1-6) | Unlocks the flagship grounding feature outside academia | L |
| 9 | Domain cap + content dedup (P2-1) | Stops SEO sources from dominating the report | M |
| 10 | Enforce `research_timeout` + node-level cancel (P2-2) | Reliability for long runs | S |
| 11 | The `tasks.md` P0/P1 fixes (P2-3) | Already specified there | S |

---

## 5. Reproducing / re-checking

```bash
.venv/bin/python scripts/dev_server.py --port 8000 &
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"query": "functional programming in web development in 2026"}'
.venv/bin/python scripts/capture_fp2026.py <id> smoke_artifacts/fp2026
```

Then diff `smoke_artifacts/fp2026/` against a new capture; the checks that
matter for the P0/P1 items above are:

- `sources.json` ids ⊇ reference markers parsed from `export_markdown.md`
- `steps.json` → each `searching` step's `citations_found` > 0
- `plan.json` → progress reaches `completed` when status is `complete`
- server log → zero `arxiv ... HTTP 406` and zero `wikipedia ... PageError`
- `state.json`/steps → `research_evidence` non-empty when the topic has web
  sources

The first two are automated:

```bash
.venv/bin/python scripts/verify_run.py smoke_artifacts/<run-dir>
```

It prints PASS/FAIL per check plus the source-type mix (so a silently dead
plugin stays visible) and exits non-zero on failure.
