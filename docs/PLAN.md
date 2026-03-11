# LLM Researcher - Architecture Plan

## Overview

An interactive AI research assistant that helps users build and explore a persistent knowledge base. Unlike traditional one-shot paper generators, this system focuses on iterative research cycles where users can add items, ask questions, and browse collected knowledge. The AI maintains state across sessions, allowing for refinement and expansion of research over time. Document generation (blog posts, academic papers, etc.) is an optional final step that leverages the accumulated knowledge base.

## Core Philosophy

- **Knowledge Base First**: The system prioritizes building a rich, queryable knowledge base over immediate document generation
- **User-Driven Exploration**: Users guide research direction through questions, suggestions, and feedback
- **Persistent State**: All research progress, AI reasoning, and knowledge are saved locally for future sessions
- **API-First Design**: All functionality is exposed via APIs to support future UI development

## General Workflow

1. User provides an initial topic and the assistant helps refine scope.
2. The planner decomposes the topic into sub-questions.
3. Search agents gather sources from web and academic providers.
4. Findings, citations, and notes are persisted to the knowledge base.
5. Users iteratively explore, edit, and extend the research.
6. Optional document generation produces blog/paper/summary outputs.


## Goals

1. **Interactive Knowledge Building**: Enable iterative research through user-AI collaboration
2. **Persistent Knowledge Base**: Store all research artifacts locally with full search capabilities
3. **Conversational Interface**: Allow users to query, update, and explore knowledge via natural language
4. **Web Research**: Search multiple sources (web, academic papers, Wikipedia, PubMed) for relevant information
5. **Knowledge Extraction**: Use NLP to extract entities, relationships, and insights from literature
6. **Knowledge Representation**: Build knowledge graphs linking papers, concepts, and findings
7. **State Persistence**: Save AI reasoning state for session continuity and transparency
8. **Parallel Execution**: Multiple subagents work concurrently on different aspects of the research
9. **Flexible Output**: Generate various document formats (blog, paper, summary) from knowledge base
10. **API-First**: All functionality available via REST APIs for future UI integration

---

## User Interaction Model

The system operates through a conversational API where users can perform various operations:

- Knowledge base operations: add, remove, edit, browse, search, and export items.
- Research operations: expand scope, ask questions, summarize progress, and identify gaps.
- AI state operations: inspect current plan/status/reasoning and reset direction.
- Document generation operations: produce or revise blog posts, papers, and summaries.


---

## Research Methodology

When conducting research, the AI follows a structured approach (but always pausable/resumable):

1. Topic understanding: clarify scope and define sub-questions.
2. Literature collection: retrieve relevant sources and extract key content.
3. Knowledge synthesis: identify themes, contradictions, and coverage gaps.
4. Optional hypothesis generation: propose and prioritize testable hypotheses.
5. Optional document generation: draft outputs with citations and iterate with feedback.


---

## Architecture

### Directory Structure

High-level project directories:

- `app`: backend services, agents, routers, models, tools, and state.
- `frontend`: React UI for research management and visualization.
- `tests`: backend and integration test suites.
- `docs`: plans, status reports, and implementation notes.
- `alembic`: database migration scripts.
- `deploy`: deployment configuration assets.


**Planned directories (not yet implemented):**

- `app/nlp`: NLP extraction and summarization components.
- `app/knowledge`: graph and vector storage components.
- `app/analysis`: experiment, statistics, and visualization components.

### Core Components

#### 1. Research State (Memory)

Research state is tracked in typed models and persisted as checkpointable JSON, including query decomposition, citations, findings, notes, reasoning logs, hypotheses, and workflow status.


#### 2. LangGraph Orchestrator (Interactive State Machine)

The orchestrator is designed as an interactive state machine that responds to user commands
rather than running as a linear pipeline. The AI can pause at any point and wait for user input.

Core flow: route user intent, execute the appropriate research or management action, persist state updates, and respond with actionable results.


**User Intent Categories:**

| Intent Type | Example Commands                     | Agent Action                    |
|-------------|--------------------------------------|---------------------------------|
| Research    | "Research X", "Find more about Y"    | Plan → Search → Extract → Store |
| Question    | "What does my research say about X?" | Query KB → Synthesize answer    |
| Add         | "Add this URL/paper"                 | Fetch → Parse → Store           |
| Remove      | "Remove source #3"                   | Delete from KB                  |
| Edit        | "Update notes for finding X"         | Modify KB item                  |
| Browse      | "Show sources about topic X"         | Filter & return KB items        |
| Generate    | "Write a blog post"                  | Synthesize KB → Draft → Iterate |
| Status      | "What's the current state?"          | Return AI state summary         |

#### 3. Tools

| Category       | Tool                      | Purpose                   | Package                 |
|----------------|---------------------------|---------------------------|-------------------------|
| **Search**     | `TavilySearchResults`     | Web search with citations | `tavily-python`         |
|                | `DuckDuckGoSearchResults` | Free fallback search      | `duckduckgo-search`     |
|                | `ArxivQueryRun`           | Academic paper search     | `arxiv`                 |
|                | `WikipediaQueryRun`       | Encyclopedia lookups      | `wikipedia`             |
|                | `PubMedSearch`            | Medical literature        | `biopython`             |
|                | `SemanticScholarSearch`   | Citation graph search     | `semanticscholar`       |
| **Extraction** | `WebScraper`              | Extract page content      | `trafilatura`           |
|                | `PDFParser`               | Parse PDF documents       | `GROBID`, `pdfplumber`  |
|                | `BibTexParser`            | Parse references          | `bibtexparser`          |
| **NLP**        | `EntityExtractor`         | Named entity recognition  | `spaCy`                 |
|                | `RelationExtractor`       | Relationship extraction   | `spaCy`, `AllenNLP`     |
|                | `Summarizer`              | Document summarization    | `transformers`          |
|                | `TopicModeler`            | Topic modeling            | `gensim`                |
| **Knowledge**  | `GraphStore`              | Knowledge graph storage   | `neo4j`, `rdflib`       |
|                | `VectorStore`             | Semantic search/RAG       | `chroma`, `faiss`       |
|                | `DocumentStore`           | Full-text search          | `elasticsearch`         |
| **Analysis**   | `StatisticalTests`        | Hypothesis testing        | `scipy`, `statsmodels`  |
|                | `MLModels`                | Pattern discovery         | `scikit-learn`, `torch` |
|                | `CausalInference`         | Causal relationships      | `dowhy`, `causalnex`    |
|                | `Visualization`           | Charts and figures        | `matplotlib`, `plotly`  |
| **Output**     | `MarkdownBuilder`         | Document generation       | `markdown`              |
|                | `PDFExporter`             | PDF conversion            | `pandoc`, `latex`       |

#### 4. Database Schema

The schema extends the base research table with persisted state and related tables for sources, findings, notes, entities, relationships, hypotheses, experiments, and embeddings.


---

## Implementation Phases

Implementation is organized in phases, building progressively from foundation to advanced capabilities. Each phase depends on previous phases being complete.

### Implementation Status Summary

**Completed Phases**: 11 out of 20 phases (55%)
- ✅ Phase 1: Foundation (HIGH)
- ✅ Phase 2: Core Tools (HIGH)
- ✅ Phase 3: Core Agents (HIGH)
- ✅ Phase 4: Parallel Execution (MEDIUM)
- ✅ Phase 5: Citations (MEDIUM)
- ✅ Phase 6: Basic Output (MEDIUM)
- ✅ Phase 7: Interactive Knowledge Base API (HIGH)
- ✅ Phase 8: Extended Search Tools (HIGH)
- ✅ Phase 9: PDF & Document Parsing (HIGH)
- ✅ Phase 16: Real-time Updates (LOW - Future UI)
- ✅ Phase 19: Web UI v1.0 (COMPLETE)

**Partially Complete**:
- 🟡 **Phase 12: Hypothesis Generation** - hypothesis_agent.py implemented and integrated into orchestrator

**HIGH Priority In Progress**:
- 🚀 **Phase 20: Frontend v2.0** - User Productivity Features
  - ✅ Sprint 1: CRUD operations for sources, findings, research editing
  - ✅ Sprint 2: Search & filtering for all resources
  - ✅ Sprint 3: Export features (BibTeX, CSV, JSON, full data backup)
  - ⏸️ Sprint 3: Bulk operations (deferred)
  - 🔄 Sprint 4: Research plan & AI state visualization (NEXT)
  - Sprint 5: UX polish & quality of life improvements

**HIGH Priority Remaining (Backend)**:
- ⏳ Phase 10: NLP & Knowledge Extraction
- ⏳ Phase 11: Knowledge Graph & Storage

**System Status**: Production-ready for web-based research with real-time UI. Frontend v1.0 provides research monitoring, knowledge base exploration, notes CRUD, agent step visualization, and chat. V2.0 will add source/finding CRUD, filtering, bulk operations, and exports. Advanced backend features (knowledge extraction, graphs) are pending.

See [STATUS_REPORT.md](STATUS_REPORT.md) for detailed progress tracking.

---

## Plugin Architecture

The codebase uses a plugin registry to decouple extensible subsystems from the agents and services that consume them. Adding a capability no longer requires touching internal agent logic — only implementing a protocol and registering the plugin.

### Search Plugins ✅ Implemented

**Location**: `app/tools/registry.py`, `app/tools/plugins.py`

Built-in plugins: `WebSearchPlugin`, `ArxivPlugin`, `WikipediaPlugin`.

To add a new search source, implement `SearchPlugin` and call `get_registry().register(MyPlugin())` at startup. The plugin controls:
- whether it requires an academic query context (`requires_academic_context`)
- whether it should run on all query variations or only the first (`first_variation_only`)
- the mapping from its raw result type to a normalised `Citation`

**Next candidates for search plugins** (no orchestrator changes needed):
- `PubMedPlugin` — `pubmed_search` already exists in `app/tools/pubmed_search.py`; gate it on `is_academic_query` and a `NCBI_API_KEY` availability check
- `SemanticScholarPlugin` — `semantic_scholar_search` exists in `app/tools/semantic_scholar.py`; useful for computing citation counts and finding related papers
- `OpenAlexPlugin` — `openalex_search` exists in `app/tools/openalex_search.py`; open-access metadata, no key required

---

### Export Plugins (Next Candidate)

**Location**: `app/output/pdf_exporter.py`, `app/routers/exports.py`

**Problem today**: `pdf_exporter.py` has a hard-coded `ExportFormat` enum and `if format == PDF: … elif format == HTML: …` dispatch. Adding DOCX/ePub/LaTeX means editing those files.

**Proposed interface**:

- Each export plugin declares format, MIME type, and file extension.
- Plugins expose availability checks (for example, dependency/tooling checks).
- Plugins implement a single export operation from markdown + options to bytes.

Built-in plugins would wrap the existing pandoc-based exporter. The `/exports` router iterates the registry instead of hard-coding formats.

---

### Citation Style Plugins (Next Candidate)

**Location**: `app/output/citation_formatter.py`

**Problem today**: APA, MLA, and Chicago CSL templates are embedded as hard-coded strings inside a `CSL_STYLES` dict; adding a new style means editing `citation_formatter.py`.

**Proposed interface**:

- Each style plugin declares the style identifier and CSL content source.
- Plugins provide a formatting method for a normalized citation object.
- The formatter resolves style plugins from a registry instead of a fixed dict.

Plugins can load their CSL from a bundled file, a URL, or a string literal, keeping `citation_formatter.py` free of style-specific knowledge.

---

### LLM Provider Plugins (Future Candidate)

**Location**: `app/llm_provider.py`

`LLMProviderFactory.create_provider()` already dispatches over a string `provider_type` with `if/elif` branches (`openai`, `ollama`, `groq`). The existing `LLMProvider` ABC is already close to a plugin contract.

**Proposed change**: replace the factory's `if/elif` with a registry lookup, so new providers (Anthropic, Mistral, Bedrock, etc.) can be registered without editing `llm_provider.py`.

Provider plugins should declare provider type, availability checks, and a standard model-construction method.

This is a lower-priority change because the ABC already gives reasonable isolation, but it becomes worthwhile once a third or fourth provider is added.

---

### Phase 1: Foundation ✅ Priority: HIGH
- [x] Add new dependencies to `requirements.txt`
- [x] Create `app/memory/research_state.py` with Pydantic models
- [x] Create `app/models.py` additions for sources and checkpoints
- [x] Set up database migrations

### Phase 2: Core Tools ✅ Priority: HIGH
- [x] Implement `app/tools/web_search.py` (Tavily + DuckDuckGo fallback)
- [x] Implement `app/tools/arxiv_search.py`
- [x] Implement `app/tools/wikipedia.py`
- [x] Implement `app/tools/web_scraper.py`

### Phase 3: Core Agents ✅ Priority: HIGH
- [x] Implement `app/agents/planner.py` - query decomposition
- [x] Implement `app/agents/search_agent.py` - tool-calling agent
- [x] Implement `app/agents/synthesis_agent.py` - document drafting
- [x] Implement `app/agents/orchestrator.py` - LangGraph workflow

### Phase 4: Parallel Execution ✅ Priority: MEDIUM
- [x] Add async support to search agent
- [x] Implement `asyncio.gather` for concurrent sub-query searches
- [x] Add rate limiting and error handling

### Phase 5: Citations ✅ Priority: MEDIUM
- [x] Implement citation extraction from search results
- [x] Implement `app/output/citation_formatter.py` (APA, MLA, Chicago)
- [x] Add citation validation (check URLs are accessible)

### Phase 6: Basic Output ✅ Priority: MEDIUM
- [x] Implement `app/output/document_builder.py` (in synthesis_agent.py)
- [x] Add inline citation markers `[1]`, `[2]` in text
- [x] Generate references section
- [x] PDF export with Pandoc

---

### Phase 7: Interactive Knowledge Base API | Priority: HIGH ⭐ NEW
*Enable user interaction with the knowledge base through conversational API*

- [x] Implement `/research/{id}/chat` endpoint (main interaction)
  - Intent classification (research, add, remove, question, generate)
  - Route to appropriate handler based on intent
  - Return structured response with action taken
- [x] Implement conversation history storage
  - Store messages in database
  - GET `/research/{id}/chat/history` endpoint
- [x] Implement Knowledge Base CRUD endpoints
  - POST `/research/{id}/sources` - add source manually
  - PATCH `/research/{id}/sources/{id}` - update notes/tags
  - DELETE `/research/{id}/sources/{id}` - remove source
  - GET `/research/{id}/sources` with filtering/search
- [x] Implement findings management endpoints
  - CRUD for user-created findings
  - Link findings to sources
- [x] Implement AI state transparency endpoints
  - GET `/research/{id}/state` - current AI state
  - GET `/research/{id}/plan` - research plan with progress
  - PATCH `/research/{id}/plan` - modify plan
- [x] Update `ResearchState` model with conversation and reasoning fields
- [x] Implement intent router agent using LLM classification
- [x] Add response formatter for consistent API responses

### Phase 8: Extended Search Tools | Priority: HIGH
*Expand search capabilities to more academic sources*

- [x] Implement `app/tools/pubmed_search.py` - PubMed/MEDLINE API
- [x] Implement `app/tools/semantic_scholar.py` - Semantic Scholar API
- [x] Implement `app/tools/crossref_search.py` - Crossref DOI/metadata
- [x] Implement `app/tools/openalex_search.py` - OpenAlex open scholarly data
- [x] Add PDF download and caching for full-text retrieval

### Phase 9: PDF & Document Parsing ✅ Priority: HIGH
*Extract structured content from academic PDFs*

- [x] Set up GROBID service (Docker container)
- [x] Implement `app/tools/pdf_parser.py` using GROBID
- [x] Add fallback parsing with `pdfplumber`/`PyPDF2`
- [x] Extract figures, tables, and equations metadata
- [x] Implement BibTeX parsing with `bibtexparser`
- [x] Create document chunking for large papers

### Phase 10: NLP & Knowledge Extraction | Priority: HIGH
*Extract structured knowledge from text*

- [x] Create `app/nlp/` module structure
- [x] Implement `app/nlp/entity_extractor.py` using spaCy
  - Scientific entity types: methods, materials, metrics, findings
  - Custom NER model fine-tuning for domain-specific entities
- [ ] Implement `app/nlp/relation_extractor.py`
  - Use spaCy dependency parsing or AllenNLP/REBEL
  - Extract: causes, correlates_with, contradicts, supports, etc.
- [ ] Implement `app/nlp/summarizer.py`
  - Hugging Face transformers (BART, T5, or LED for long documents)
  - Abstract-level and section-level summaries
- [ ] Implement `app/nlp/topic_modeler.py`
  - Gensim LDA for topic discovery
  - BERTopic for neural topic modeling

### Phase 11: Knowledge Graph & Storage | Priority: HIGH
*Store and query extracted knowledge*

- [ ] Create `app/knowledge/` module structure
- [ ] Set up Neo4j (Docker container)
- [ ] Implement `app/knowledge/graph_builder.py`
  - Convert entities/relationships to graph nodes/edges
  - Link papers → authors → institutions → concepts
- [ ] Implement `app/knowledge/graph_store.py`
  - Neo4j driver integration
  - Cypher query helpers
- [ ] Set up Chroma/FAISS vector store
- [ ] Implement `app/knowledge/vector_store.py`
  - Document embedding with OpenAI/sentence-transformers
  - Semantic similarity search for RAG
- [ ] Add Elasticsearch for full-text search (optional)
- [ ] Create database tables for entities, relationships, embeddings

### Phase 12: Hypothesis Generation | Priority: MEDIUM (Optional) 🟡 Partial
*Identify gaps and propose hypotheses - can be skipped if not needed*

- [x] Implement `app/agents/hypothesis_agent.py`
  - ~~Analyze knowledge graph for gaps (missing relationships)~~ (requires Phase 11)
  - [x] Identify contradictions in literature
  - [x] Propose testable hypotheses using LLM reasoning
- [x] Add hypothesis ranking system
  - Novelty score (inverse of existing evidence)
  - Plausibility score (consistency with known relationships)
  - Testability score (data availability)
- [x] Implement hypothesis validation against existing literature
- [x] Add user feedback loop for hypothesis refinement
- [x] Update orchestrator with hypothesis generation step

### Phase 13: Experiment Design | Priority: LOW (Optional)
*Design analyses to test hypotheses - only if doing scientific research*

- [ ] Create `app/analysis/` module structure
- [ ] Implement experiment design agent
  - Determine required data sources
  - Select appropriate statistical methods
  - Define variables, controls, success metrics
- [ ] Implement `app/analysis/statistics.py`
  - scipy.stats integration for common tests
  - statsmodels for regression analysis
  - Multiple comparison corrections (Bonferroni, FDR)
- [ ] Implement `app/analysis/ml_models.py`
  - scikit-learn for classification/regression
  - Clustering for pattern discovery
  - Optional: PyTorch for deep learning
- [ ] Implement `app/analysis/causal_inference.py`
  - DoWhy for causal effect estimation
  - CausalNex for Bayesian networks (optional)

### Phase 14: Data Analysis & Visualization | Priority: LOW (Optional)
*Execute experiments and visualize results - only if doing scientific research*

- [ ] Implement data collection pipelines
  - API connectors for public datasets
  - Web scraping with ethical rate limiting
- [ ] Implement `app/analysis/visualization.py`
  - matplotlib for static figures
  - plotly for interactive charts
  - Automatic figure generation from results
- [ ] Add result interpretation using LLM
  - Compare results to hypotheses
  - Generate discussion of findings
  - Identify limitations and biases
- [ ] Implement iteration logic (refine hypothesis if inconclusive)

### Phase 15: Document Generation (Optional Output) | Priority: MEDIUM
*Generate documents from knowledge base - this is optional, not the main goal*

- [ ] Implement generation API endpoints
  - POST `/research/{id}/generate` - trigger generation
  - GET `/research/{id}/drafts` - list drafts
  - POST `/research/{id}/drafts/{id}/iterate` - iterate with feedback
  - GET `/research/{id}/drafts/{id}/export` - export to various formats
- [ ] Implement `app/agents/generation_agent.py`
  - Support multiple output formats: blog, paper, summary, custom
  - Use knowledge base as grounding context
  - Iterate on drafts based on user feedback
- [ ] Implement `app/output/document_builder.py` (full version)
  - Blog post template (casual, engaging)
  - Academic paper template (structured, formal)
  - Executive summary template (concise, non-technical)
  - Custom template support
- [ ] Implement `app/output/pdf_exporter.py`
  - Pandoc integration for format conversion
  - Multiple export formats: PDF, HTML, DOCX, Markdown
- [ ] Support multiple citation styles (already have APA, MLA, Chicago)

### Phase 16: Real-time Updates | Priority: LOW (Future UI)
*Enable real-time progress tracking for future UI*

- [x] Add WebSocket endpoint for progress updates
- [x] Stream partial results as research progresses
- [x] Add research cancellation endpoint
- [x] Implement research resumption from checkpoints
- [x] Add batch research submission
- [x] Rate limiting and usage quotas

### Phase 17: Workflow Orchestration | Priority: LOW (Future)
*Advanced workflow management for complex research*

- [ ] Consider Apache Airflow/Prefect for complex pipelines
- [ ] Implement scheduled re-runs for literature monitoring
- [ ] Add notification system for research completion
- [ ] Multi-research project management
- [ ] Collaboration features (multiple users per research)

### Phase 18: Quality & Reproducibility | Priority: LOW (Future)
*Ensure research quality and reproducibility*

- [ ] Implement confidence scoring for findings
- [ ] Add source credibility assessment
- [ ] Fact-checking against known databases
- [ ] Full provenance tracking (data lineage)
- [ ] Reproducibility report generation
- [ ] Export research environment (Docker + data snapshot)

### Phase 19: Web UI | Priority: COMPLETE ✅
*React + TypeScript frontend for research management*

#### ✅ Implemented Features (v1.0)
- [x] **Research Management**
  - Create new research queries with optional notes
  - Browse paginated list of all research with status indicators
  - View detailed research information
  - Delete research queries
  - Cancel and resume research
  - Inline editing of research query (EditableResearchHeader)
  - Real-time status updates via polling

- [x] **Research Detail View (8 Tabs)**
  - Overview tab: Summary metrics (sources/findings count), status, progress
  - Sources tab: Browse all collected sources with links
  - Findings tab: View extracted findings with categories
  - Result tab: Final synthesized document
  - Knowledge Base tab: Tree view (sub-queries → citations) and flat sources list, source type filtering, relevance scores, hypothesis investigations
  - Notes tab: CRUD for research notes with category/agent filtering (observation, gap, pattern, contradiction, instruction, summary)
  - Agent Steps tab: Timeline visualization of agent execution steps, color-coded by type, expandable with metadata
  - Chat tab: Interactive Q&A about research results

- [x] **Real-time Progress Monitoring**
  - Polling-based status updates (1s while researching)
  - Progress percentage display
  - Error notifications

- [x] **Chat Interface**
  - Send questions about research findings
  - View conversation history
  - Assistant responses with timestamps
  - Auto-scroll to latest messages
  - Loading/thinking states

- [x] **Knowledge Base Explorer**
  - Dual view modes: tree view (by sub-query) and flat source list
  - Source type filtering (web, arxiv, wikipedia, pubmed, semantic_scholar)
  - Relevance score bars
  - Expandable citation snippets
  - Hypothesis investigations display
  - Source distribution stats

- [x] **Notes Management**
  - Create, edit, delete notes
  - Category-based color coding
  - Filter by agent and category
  - Agent attribution (planner, search, hypothesis, synthesis, user)

- [x] **Modern UI/UX**
  - Clean, professional design with Tailwind CSS
  - Responsive layout (desktop + mobile)
  - Color-coded status badges with icons
  - Loading states and error handling
  - Empty state messages
  - Hover effects and transitions

- [x] **Production Deployment**
  - Multi-stage Docker build
  - Nginx reverse proxy for API and WebSocket
  - Optimized static asset serving
  - Gzip compression
  - Environment-agnostic (proxied API)

---

### Phase 20: Frontend v2.0 - User Productivity Features | Priority: HIGH
*Enhance frontend with CRUD operations and user workflows*

#### 📦 Sprint 1: Core CRUD Operations (Week 1-2)
**Goal**: Enable users to manage their research data directly in the UI

**Backend APIs**: ✅ All endpoints exist
- `POST/PUT/DELETE /research/{id}/sources`
- `POST/PUT/DELETE /research/{id}/findings`
- `PATCH /research/{id}` for notes/tags

**Frontend Implementation**:

- [x] **Research Editing**
  - Edit research query inline (with confirmation)
  - Edit user notes (textarea with save/cancel) ✅ **COMPLETED** - Database migration done
  - Add/edit/remove tags (tag input component) ✅ **COMPLETED** - Database migration done
  - Display last updated timestamp

- [x] **Source CRUD Operations**
  - "Add Source" button with modal form (URL/DOI input, auto-fetch metadata)
  - Edit source modal (title, URL, notes, metadata)
  - Delete source with confirmation
  - Inline edit notes on sources
  - Visual feedback for save/delete operations

- [x] **Finding CRUD Operations**
  - "Add Finding" button with form (content, category, importance, source link)
  - Edit finding modal (all fields editable)
  - Delete finding with confirmation
  - Drag-and-drop importance slider (1-5 stars) - not implemented yet
  - Link finding to source (dropdown selector)
  - Category autocomplete based on existing categories - not implemented yet
  - Inline edit for finding content

**Components Built**:
- ✅ `EditableResearchHeader.tsx` - Inline editing for query (implemented)
- ✅ `SourceFormModal.tsx` - Add/edit source form (implemented)
- ✅ `FindingFormModal.tsx` - Add/edit finding form (implemented)
- ✅ `ConfirmDialog.tsx` - Reusable confirmation dialog (implemented)

**Status**: ✅ **SPRINT 1 COMPLETED** - All core CRUD operations functional

**Estimated Effort**: 10-12 hours (completed)
**User Value**: CRITICAL - Users can now modify research data

---

#### 📦 Sprint 2: Filtering & Search (Week 3) ✅ **COMPLETED**

**Estimated Effort**: 8-12 hours
**User Value**: HIGH - Core productivity features

---

#### 📦 Sprint 2: Search & Filtering (Week 3)
**Goal**: Help users find information quickly in large research collections

**Backend APIs**: ✅ Query parameters exist for filtering
- `/research?status=completed&tags=ai&search=query`
- `/research/{id}/sources?source_type=arxiv&search=keyword`
- `/research/{id}/findings?category=methods&min_importance=3`

**Frontend Implementation**:

- [x] **Research List Filtering** ✅ **COMPLETED**
  - Status filter dropdown (all, pending, researching, completed, failed, cancelled, error)
  - Text search across queries and user notes (case-insensitive, debounced 300ms)
  - Active filters display with "clear X filters" button
  - Filter result count shown above list
  - SearchInput component with debounced onChange
  - Backend enhanced with query parameters: `?status=X&search=Y`
  - Added user_notes field to Research model, schemas, and API

- [x] **Source Filtering & Search** ✅ **COMPLETED**
  - Source type filter (web, arxiv, pubmed, semantic_scholar, wikipedia, etc.)
  - Text search in title/content/author
  - Sort by: date added (newest/oldest), title (A-Z/Z-A)
  - Quick filters: "Academic only", "Recently added", "No content"
  - SourcesFilterBar component with all controls
  - Backend API updated with sort_by and sort_order parameters

- [x] **Finding Filtering & Search** ✅ **COMPLETED**
  - Source filter (show findings from specific source)
  - Text search in content
  - Sort by: date created (newest/oldest)
  - FindingsFilterBar component implemented
  - Backend API updated with source_id, search, and sort parameters
  - Note: Category and importance fields not yet in schema (future enhancement)

**Components Built**:
- ✅ `SourcesFilterBar.tsx` - Filter component for sources (implemented)
- ✅ `FindingsFilterBar.tsx` - Filter component for findings (implemented)
- ✅ `SearchInput.tsx` - Debounced search input with clear button (implemented)

**Components for Future Enhancement**:
- `MultiSelect.tsx` - Multi-select dropdown (for future category filters)
- `DateRangePicker.tsx` - Date range selection (if needed)

**Estimated Effort**: 6-8 hours
**User Value**: HIGH - Essential for managing many items

---

#### 📦 Sprint 3: Bulk Operations & Export (Week 4) ⏸️ PARTIALLY COMPLETE
**Goal**: Power-user features for efficiency

**Status**: Export features completed, bulk operations deferred

**Backend APIs**: Partial support, may need batch endpoints
- Export endpoints exist: `/research/{id}/export/bibtex`, `/research/{id}/export/json`

**Frontend Implementation**:

- [ ] **Bulk Selection**
  - Checkbox on each source/finding
  - "Select all" / "Select none" controls
  - Selection counter (X items selected)
  - Available on Sources and Findings tabs

- [ ] **Bulk Actions**
  - Delete selected (with count confirmation)
  - Categorize selected findings (batch update)
  - Tag selected sources (batch add/remove tags)
  - Export selected to JSON/CSV
  - Progress indicator for bulk operations

- [x] **Export Features** ✅ COMPLETED (Sprint 3)
  - ✅ Export all sources as BibTeX (download button)
  - ✅ Export all findings as CSV/JSON
  - ✅ Export full research as JSON backup
  - ⏸️ Copy sources to clipboard (formatted text) - DEFERRED
  - ⏸️ Share research summary (generate shareable link) - DEFERRED

**Components to Build**:
- `SelectableList.tsx` - List with checkbox selection
- `BulkActionBar.tsx` - Action bar shown when items selected
- `ExportMenu.tsx` - Dropdown menu for export options

**Estimated Effort**: 6-8 hours
**User Value**: MEDIUM - Power users will love it

---

#### 📦 Sprint 4: Research Plan & State Visualization (Week 5)
**Goal**: Give users visibility into AI research process

**Backend APIs**: ✅ Endpoints exist
- `GET /research/{id}/plan` - Current plan with sub-queries
- `GET /research/{id}/state` - Full LangGraph state
- `PATCH /research/{id}/plan` - Modify plan

**Frontend Implementation**:

- [x] **Research Plan View** (New tab in ResearchDetail) ✅ PARTIAL (Sprint 4)
  - ✅ Display main research question
  - ✅ List all sub-queries with status (completed/pending)
  - ✅ Show finding snippets for completed sub-queries
  - ✅ "Add sub-query" button
  - ✅ "Remove sub-query" button (with impact warning)
  - ⏸️ Reorder sub-queries (drag-and-drop) - deferred

- [x] **AI State Inspector** (Expandable panel) ✅ PARTIAL (Sprint 4)
  - ✅ Display current research status and activity
  - ✅ Show reasoning log (decision history)
  - ✅ View intermediate results (pending/completed queries + metrics)
  - ⏸️ Checkpoint browser (view state at different times) - deferred
  - ⏸️ "Restart from checkpoint" button - deferred

- [x] **Improved Overview Tab** ✅ PARTIAL (Sprint 4)
  - ✅ Visual progress indicator (% complete)
  - ✅ Timeline of research events
  - ✅ Key metrics cards (sources count, findings count, sub-queries)
  - ✅ Recent activity feed
  - ⏸️ Estimated time remaining (if researching) - deferred

**Components to Build**:
- ✅ `ResearchPlanTab.tsx` - New tab for plan management (implemented)
- ✅ `StateInspector.tsx` - AI state visualization (implemented)
- ✅ `TimelineView.tsx` - Event timeline (implemented)
- ✅ `MetricsCards.tsx` - Statistics dashboard (implemented)

**Estimated Effort**: 8-10 hours
**User Value**: MEDIUM-HIGH - Transparency and control

---

#### 📦 Sprint 5: UX Polish & Quality of Life (Week 6)
**Goal**: Make the interface delightful to use

**Frontend Implementation**:

- [ ] **Navigation Improvements**
  - Keyboard shortcuts (? to show help, / to search, n for new research)
  - Breadcrumb navigation
  - Back/forward history
  - "Jump to research" quick search (Cmd/Ctrl + K)
  - Recent research sidebar (last 5 viewed)

- [ ] **Visual Enhancements**
  - Dark mode toggle (save preference)
  - Improved loading skeletons (not just "Loading...")
  - Empty state illustrations
  - ✅ Success/error toast notifications (not just alerts)
  - Smooth page transitions
  - Animated progress bars

- [ ] **User Preferences**
  - Persistent UI preferences (localStorage)
  - Default sort/filter preferences
  - Auto-refresh interval setting
  - Notification settings
  - Compact/comfortable/spacious view density

- [ ] **Accessibility**
  - ARIA labels on all interactive elements
  - Keyboard navigation for all features
  - Screen reader friendly
  - High contrast mode
  - Focus indicators

**Components to Build**:
- `KeyboardShortcuts.tsx` - Help modal with shortcuts
- `CommandPalette.tsx` - Quick search/navigation
- ✅ `Toast.tsx` - Notification system (implemented)
- `SettingsPanel.tsx` - User preferences

**Estimated Effort**: 10-12 hours
**User Value**: MEDIUM - Quality of life improvements

---

#### 🔮 Future Considerations (Post v2.0)

**Priority: LOW - Advanced Features**
- [ ] **Visualization**
  - Knowledge graph visualization (requires Phase 11 backend)
  - Topic distribution charts
  - Source type breakdown pie charts
  - Research timeline visualization
  - Citation network graph (if knowledge graph implemented)

- [ ] **Collaboration** (Requires multi-user backend Phase 17)
  - Share research with collaborators
  - Comments on sources/findings
  - Activity feed (who did what)
  - Permission management
  - Real-time collaborative editing

- [ ] **Advanced AI Features** (Requires backend phases 12-15)
  - Hypothesis management UI (Phase 12)
  - Analysis results viewer (Phase 13-14)
  - Document generation interface (Phase 15)
  - Side-by-side draft comparison

- [ ] **Mobile App**
  - React Native mobile app
  - Offline mode with sync
  - Push notifications
  - Mobile-optimized research browsing

**Priority: MEDIUM - User Experience**
- [ ] **Advanced Search & Filtering**
  - Full-text search across all research
  - Saved search queries
  - Smart suggestions based on history
  - Related research recommendations

- [ ] **Improved Navigation**
  - Pinned/starred research
  - Research folders/organization
  - Custom views and dashboards
  - Workspace switching (for different projects)

**Priority: LOW - Infrastructure**
- [ ] **Performance Optimizations**
  - Lazy loading for large lists
  - Virtual scrolling for thousands of items
  - Image lazy loading
  - Code splitting for faster initial load
  - Service worker for caching

- [ ] **Progressive Web App (PWA)**
  - Offline mode with sync
  - Install as app
  - Background sync
  - Push notifications
  - App-like experience

- [ ] **Internationalization**
  - Multi-language support (i18n)
  - RTL language support
  - Date/time localization
  - Number formatting

---

#### 📊 Frontend v2.0 Summary

**Total Estimated Effort**: 38-50 hours (6-8 weeks at part-time pace)

**Prioritized Implementation Order**:
1. **Sprint 1** (HIGH) - CRUD operations unlock core user workflows
2. **Sprint 2** (HIGH) - Search/filter essential for scale
3. **Sprint 4** (MEDIUM-HIGH) - Transparency & control = user trust
4. **Sprint 3** (MEDIUM) - Power users = engaged users
5. **Sprint 5** (MEDIUM) - Polish = professional product

**Success Metrics**:
- Users can manage 100+ sources without frustration
- Finding a specific source/finding takes <10 seconds
- Users understand what the AI is doing and why
- No need to use API docs for common operations
- Users prefer UI over direct API calls

**Backend Dependency**: All Sprint 1-4 features use existing APIs ✅

#### 📊 Current UI Tech Stack
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **WebSocket API** - Real-time updates
- **Nginx** - Production web server
- **Docker** - Containerized deployment

#### 🚀 UI Access
- **Development**: `cd frontend && npm run dev` → http://localhost:3000
- **Production**: `make up` → http://localhost:3000
- **Documentation**: See [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) and [FRONTEND_IMPLEMENTATION.md](FRONTEND_IMPLEMENTATION.md)

---

## Dependencies

### Currently Installed (Phases 1-6)

### Phase 7: Extended Search

### Phase 8: PDF Parsing

### Phase 9: NLP & Knowledge Extraction

### Phase 10: Knowledge Graph & Storage

### Phase 12-13: Analysis

### Phase 14: Report Generation

### Phase 16: Workflow (Optional)

---

## API Design

### Core API Philosophy

The API is designed around the interactive research assistant model:
- **Conversational**: Main interaction through a chat-like endpoint
- **Knowledge Base CRUD**: Full control over research items
- **State Transparency**: Users can inspect AI reasoning and state
- **Document Generation**: Optional output generation from accumulated knowledge

### Research Session Endpoints


### Conversation / Chat Endpoint (Primary Interface)


### Knowledge Base Endpoints


### AI State Endpoints


### Document Generation Endpoints


### Export Endpoints


### (Future) Real-time Endpoints


---

## Environment Variables


---

## Notes

### Current Implementation
- **LangGraph** is used for the multi-step workflow with checkpointing
- **Tavily** is preferred for web search as it returns structured citations
- State is persisted to PostgreSQL via LangGraph's `PostgresSaver`
- All searches run in parallel using `asyncio.gather`
- Citations follow a consistent format with URL, title, date accessed

### Key Architecture Decisions

- **Interactive over Pipeline**: The system is designed as an interactive research assistant,
  not a one-shot document generator. Users build knowledge over time.
- **Knowledge Base First**: All research artifacts are stored in a persistent knowledge base
  that users can query, browse, and modify.
- **Conversation-Driven**: The main interaction pattern is through a chat-like API where
  users express intent in natural language.
- **Document Generation is Optional**: Generating papers/blogs is a secondary feature that
  leverages the accumulated knowledge base.
- **API-First**: All functionality is exposed via REST APIs to enable future UI development.
- **State Transparency**: Users can inspect AI reasoning and decision-making process.

### Future Architecture Considerations
- **Knowledge Graph**: Neo4j will store entities and relationships, enabling:
  - Literature gap detection (missing edges)
  - Contradiction identification (conflicting edges)
  - Citation network analysis
- **RAG Pipeline**: Chroma/FAISS vector store for semantic retrieval:
  - Chunk papers into embeddings
  - Retrieve relevant context for answering questions
  - Ground LLM outputs in source material
- **GROBID**: Self-hosted service for PDF parsing:
  - Extracts structured sections from academic PDFs
  - Handles complex layouts with figures/tables
  - Returns TEI XML for consistent parsing

### Recommended Implementation Order

1. **Phase 7 (Interactive KB API)** - Core user interaction functionality ⭐ PRIORITY
2. **Phase 8 (Extended Search)** - More sources = better knowledge coverage
3. **Phase 9 (PDF Parsing)** - Access full paper content, not just abstracts
4. **Phase 10 (NLP Extraction)** - Foundation for knowledge graph
5. **Phase 11 (Knowledge Graph)** - Enable semantic querying and gap detection
6. **Phase 15 (Document Generation)** - Optional output from knowledge base
7. **Phases 12-14 (Hypothesis/Analysis)** - Only if doing scientific research
8. **Phases 16-18** - Future enhancements, UI support

### External Services (Docker Compose)
