# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **A fresh `docker compose build` produced an app that could not start.**
  `requirements.txt` allowed `bibtexparser>=1.4.0`, and 2.x removed the
  `bibtexparser.bparser` / `bibdatabase` / `bwriter` modules that
  `app/tools/bibtex_parser.py` imports, so a rebuilt image died at import with
  `ModuleNotFoundError: No module named 'bibtexparser.bparser'`. This only
  appeared on a rebuild — an existing image kept a cached 1.x wheel. The
  dependency is now pinned to `>=1.4.0,<2.0.0`. Verified by rebuilding the
  image and serving `GET /` → 200.
- **PDF and DOCX export returned HTTP 500 for every request.** Pandoc can write
  text formats to stdout but refuses binary ones ("Output to docx only works by
  using a outputfile"). `export_markdown_to_format` now converts PDF/DOCX into a
  temporary file and reads the bytes back, removing the file on every path —
  including failure. The DOCX branch also passed `--reference-doc=default`,
  which is not a path pandoc accepts, and has been dropped. The Docker image
  additionally installs `texlive-latex-recommended`, `texlive-fonts-recommended`
  and `lmodern`, because pandoc's default template needs `xcolor.sty` and
  friends, which `texlive-latex-base` alone does not ship. Verified in the
  container: `pdf` → 200 with a `%PDF` header, `docx` → 200 with a valid OOXML
  zip, `html`/`markdown` → 200.
- **Full-text grounding never engaged (GROBID was dead code).** Citations were
  persisted only after the whole workflow, but `collect_fulltext_evidence`
  resolves candidates against the `ResearchSource` rows for the research — so
  the identity map was empty, every candidate was skipped, and the log read
  `Retrieved full text for 0/3 candidate sources` while synthesis fell back to
  search snippets. Sources found by the search segment are now saved *before*
  evidence collection. Passes with a new test asserting the rows exist when
  evidence is collected; that test fails if the save is removed.
- **A completed research item could be stranded in `researching` forever.** The
  chat `research` intent set `status = "researching"`, but the worker's atomic
  claim only accepts `pending`, so the queued run no-opped and nothing ever
  restored a terminal status (`POST /resume` refuses `complete`). A chat
  `research` intent against a finished item now starts a **new** item (carrying
  over notes/tags and returning `state_changes["new_research_id"]`) so the
  finished report is not overwritten; any other status is re-queued in place as
  `pending`, which also recovers already-stranded items.
- **`tags` and `user_notes` were silently dropped.** `POST /research` discarded
  `tags`, `PATCH /research/{id}` only applied `query` despite documenting
  otherwise, and batch creation could not express either field. All three now
  persist them; `BatchResearchCreate` gained `user_notes`/`tags`.
- **One bad Wikipedia search hit aborted the whole sub-query.** An unresolvable
  title raised `PageError` and an ambiguous one `DisambiguationError`, either of
  which discarded every other result. Each page is now fetched defensively, with
  a fallback to an auto-suggesting summary lookup and finally to a summary of
  the original query.
- **`/plan` progress was always `pending` and `/state` always returned an empty
  `completed_queries`.** Both read `state_json["findings"]`, which nothing ever
  wrote. Progress is now derived from `sub_query_results` (the real serialized
  search state), with the persisted `research_findings` rows as a fallback.
  Verified against a real item: 5/5 sub-queries now report `complete`.
- **Hypothesis-phase sources were attributed to no sub-query or finding.** They
  were returned as bare citations, so the sources carrying the report's most
  specific claims never became findings and were missing from the knowledge base
  and `/plan`. They are now returned as `SubQueryResult`s.
- **A single site's near-duplicate pages could dominate a report.** Search
  assembly now caps generic-web sources per domain
  (`research_max_sources_per_domain`, default 4), keeping the highest-scoring
  ones and preserving order. Academic source types are exempt, because each row
  is a distinct paper even though they share a host.
- **`research_timeout` was dead configuration.** It is now enforced as a
  whole-run budget around each workflow segment, so a hung provider cannot hold
  a research in a non-terminal status forever. The default was raised from 300 s
  to 1800 s: measured end-to-end runs take 261–306 s, so the old value would
  have killed healthy runs the moment it was honoured.
- **Partial search failures were reported as `0 errors`.** Errors from
  individual sub-queries were discarded whenever any citations were found, so
  the phase summary disagreed with the per-step statuses.
- **Snippets and titles could be publisher chrome.** Search results carried
  titles like `"Medium"` and abstracts that were pure sign-in chrome, which fed
  the relevance filter and produced BibTeX keys like
  `@misc{Unknown2026Medium}`. Leading navigation/sign-in/cookie text is now
  stripped (conservatively — a chrome word followed by real content is left
  alone) and a title that is only the site name is replaced by one derived from
  the URL slug.
- **The worker leaked a database session on every failed run**, because the
  error path opened a second session to record the failure without closing the
  first. `app.main` also configured the root logger at `DEBUG`, writing pipeline
  detail to the container log; the level is now `INFO` by default and
  configurable via `LOG_LEVEL`.
- **CI tested a runtime the project does not ship.** Both jobs ran Python 3.11
  while the Dockerfile and README are 3.12. CI now uses 3.12, and the test job
  blanks the optional API-key variables so a stray `.env` cannot make it hit a
  live API.
- **`citation_marker` was not rendered anywhere in the UI**, so the marker
  assigned to each source was invisible. The sources list and the report
  overview now show the `[n]` badge (and `null`/absent means "not cited").

- **Report citations now resolve to the source the sentence was written from.**
  The document numbered citations with the pipeline's collection markers while
  `GET /research/{id}/sources` returned knowledge-base row ids, so the two
  disagreed as soon as a source was merged or left uncited — a live report
  cited `[14]`–`[18]` for rows `12`–`16`, and `[12]`/`[13]` were gaps with no
  source at all. Numbering is now assigned once, after collection finishes:
  `app/services/citation_numbering.py` renumbers the cited sources `1..N` in
  order of first appearance, rewrites the inline markers and rebuilds the
  reference list, and the same marker is stored on each `ResearchSource`
  (`citation_marker`, new column + migration) and returned by the API. Sources
  that differ only by URL fragment or tracking parameter — which the knowledge
  base merges into one row — now share a single marker instead of producing a
  citation no row carries.
- **Relevance filtering kept only a fraction of on-topic sources.** The filter
  asked one LLM call per citation to "be strict — when in doubt, mark as
  irrelevant" against the whole sub-question using a 500-character snippet that
  was often navigation boilerplate; a live run kept `2/17` and `5/14`, leaving
  two of five sub-questions with no sources. Assessment is now batched
  (`research_relevance_batch_size`, 20 per call), the prompt asks whether a
  source *could contribute evidence for any part of* the sub-question, sources
  the model skips or that fail assessment are kept, and a sub-query that would
  otherwise be emptied keeps its highest-scoring few
  (`research_relevance_fallback_keep`).
- **arXiv never returned a result.** Raw natural-language questions were sent
  as the API query, every call burned four attempts because of the library's
  internal retry, concurrent sub-query searches were never paced against
  arXiv's one-request-per-three-seconds limit, and the resulting `HTTP 406`
  surfaced as a full traceback and a pipeline error. Queries are now rewritten
  into `all:` field syntax (`build_arxiv_query`), each call issues exactly one
  request, requests are paced process-wide
  (`ARXIV_MIN_INTERVAL_SECONDS`), and a rate-limit response trips a cooldown
  (`ARXIV_RATE_LIMIT_COOLDOWN_SECONDS`) instead of being retried. The arXiv
  plugin also runs on the first query variation only.
- **The planner's academic-sources decision was discarded.**
  `PlannerOutput.include_academic` was written to step metadata and never read;
  the search phase re-derived it with a keyword list that treated *framework*,
  *model*, *method* and *approach* as academic markers, enabling the academic
  plugins for nearly every product question. `ResearchState.include_academic`
  now carries the planner's decision into the search phase, and the keyword
  heuristic is restricted to unambiguous markers (research, paper, study,
  benchmark, …).

### Added

- `app/services/citation_numbering.py` — single source of truth for the
  reader-facing citation numbers shared by the document and the knowledge base.
- `scripts/verify_run.py` — checks a captured run for the invariants above
  (contiguous, resolvable citation numbering; every sub-query with sources;
  which source types contributed).
- `research_sources.citation_marker` (Alembic `b3c91d4f7a20`), exposed as
  `citation_marker` on the sources API.

- **Resume no longer destroys the knowledge base.** `POST /research/{id}/resume`
  deleted every source, finding, and note before re-running — including
  user-authored notes (`agent="user"`), source `user_notes`, and `tags` — and
  left the knowledge base empty if the resumed run then failed. Resume is now
  purely additive.
- **PDF settings were never read.** `PDF_CACHE_DIR`, `MAX_PDF_SIZE_MB` and
  `GROBID_SERVER` were passed to `get_setting` in the wrong argument slots and
  were not defined in `Settings` at all, so the cache directory resolved to the
  relative path `"PDF_CACHE_DIR"`, the GROBID URL was the literal string
  `"GROBID_SERVER"`, and the size cap silently fell back to the default. These
  are now real, overridable settings.
- **Duplicate sources and unstable evidence links.** `save_citations_to_db`
  inserted unconditionally, so the same paper re-discovered under a different
  URL spelling produced duplicate rows, and `save_findings_to_db` resolved
  evidence through a URL-keyed dict where the last duplicate won. Sources now
  carry a normalized identity (`doi:` / `arxiv:` / `url:`), merges are
  idempotent, and findings link through a conflict-free identity map.

### Added

- **Full-text grounding.** After search, open-access PDFs are downloaded,
  parsed (GROBID with pdfplumber/PyPDF2 fallbacks) and chunked; the passages
  most relevant to the query are stored in a new `research_evidence` table
  (text, character offsets, section label) and injected into the synthesis
  prompt with citation markers. Reports can now cite what papers say rather
  than only their abstracts. Controlled by `RESEARCH_FULLTEXT_*` settings and
  bounded per run.
- `app/services/source_identity.py` — one place that decides when two URLs mean
  the same source.
- The research graph runs in two segments using LangGraph `interrupt_after`,
  with evidence retrieval between them.

### Changed

- **DeepSeek model id updated to `deepseek-flash` (V4.1-Flash).** DeepSeek
  retired the V4-Flash and V4-Pro models; `deepseek-v4-flash` and
  `deepseek-v4-pro` now survive only as undocumented temporary aliases that
  route to V4.1-Flash. The provider default, `.env.example`, and README now use
  the canonical `deepseek-flash`. Existing `deepseek-v4-*` configurations keep
  working for now but should be updated.
- Source identity now drives citation de-duplication in `ResearchState`
  (`get_all_citations`), so scheme/`www`/tracking-parameter/DOI variants of one
  paper collapse to a single citation.
- Adding a source that already exists returns the existing row instead of
  creating a duplicate.
- Agent notes de-duplicate by `(agent, content)`; user notes are never written
  or modified by the pipeline.

## [2.0.0] - 2026-08-10

This is the first public release of LLM Researcher — a self-hostable, multi-agent
academic research assistant with a persistent knowledge base and real-time UI.

### Added

- **Multi-agent research pipeline** powered by LangGraph: `plan → search →
  chase_references → hypothesize → synthesize → format`, with checkpointing,
  cancellation, and resume-from-interruption support.
- **Plugin-based search** across ~10 providers: web (Tavily/DuckDuckGo), arXiv,
  Wikipedia, Crossref, OpenAlex, PubMed, Semantic Scholar, Springer Nature, and
  Elsevier Scopus.
- **Persistent knowledge base** (sources, findings, notes) with full CRUD,
  filtering, sorting, tags, and per-item notes — all stored in PostgreSQL and
  queryable across sessions.
- **Real-time WebSocket streaming** of progress, agent steps, and AI state to a
  React + TypeScript frontend with a 10-tab detail view (Overview, Plan,
  Sources, Findings, Entities, Result, Knowledge Base, Notes, Agent Steps,
  Chat).
- **Export formats**: PDF, HTML, DOCX, and Markdown documents; BibTeX, CSV, and
  JSON data exports; full research-data backup.
- **PDF pipeline**: download + cache, GROBID full-text parsing, document
  chunking, and BibTeX parsing for citation extraction.
- **LLM provider flexibility**: OpenAI, Ollama (local), Groq, and DeepSeek
  configurable via environment variables.
- **Docker Compose deployment** with app, PostgreSQL, Nginx-served frontend,
  and GROBID services.

### Changed

- **N/A** (first tagged release).

### Fixed

- **N/A** (first tagged release).

[2.0.0]: https://github.com/lfarroco/llm-researcher/releases/tag/v2.0.0
