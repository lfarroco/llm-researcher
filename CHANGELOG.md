# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

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
