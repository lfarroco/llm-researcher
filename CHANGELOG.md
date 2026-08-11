# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
