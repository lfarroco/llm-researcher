# LLM Researcher - Architecture Plan

## Overview

An interactive AI research assistant that helps users build and explore a persistent knowledge base. Unlike traditional one-shot paper generators, this system focuses on iterative research cycles where users can add items, ask questions, and browse collected knowledge. The AI maintains state across sessions, allowing for refinement and expansion of research over time. Document generation (blog posts, academic papers, etc.) is an optional final step that leverages the accumulated knowledge base.

## Core Philosophy

- **Knowledge Base First**: The system prioritizes building a rich, queryable knowledge base over immediate document generation
- **User-Driven Exploration**: Users guide research direction through questions, suggestions, and feedback
- **Persistent State**: All research progress, AI reasoning, and knowledge are saved locally for future sessions
- **API-First Design**: All functionality is exposed via APIs to support future UI development

## General Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INTERACTIVE RESEARCH WORKFLOW                     │
└─────────────────────────────────────────────────────────────────────┘

1. USER INPUT & REFINEMENT
   ├── User provides initial research topic or question
   ├── AI suggests clarifications and scope refinements
   └── User confirms or adjusts direction

2. AI PLANNING & RESEARCH
   ├── AI decomposes query into sub-questions
   ├── AI searches multiple sources (web, academic, etc.)
   ├── AI extracts entities, relationships, key findings
   └── Everything is added to the knowledge base

3. KNOWLEDGE BASE MANAGEMENT
   ├── All sources, citations, and findings are persisted
   ├── Users can browse, search, filter the knowledge base
   ├── Users can add/remove/edit items manually
   └── AI state (reasoning, hypotheses) is saved

4. INTERACTIVE EXPLORATION
   ├── User asks questions about the collected knowledge
   ├── User requests deeper research on specific topics
   ├── User makes suggestions or corrections
   └── AI updates state and knowledge base accordingly

5. DOCUMENT GENERATION (Optional)
   ├── User chooses output format (blog post, paper, summary)
   ├── AI synthesizes knowledge base into document
   ├── User can iterate on draft with feedback
   └── Final output with proper citations
```

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

```
┌─────────────────────────────────────────────────────────────────────┐
│                    USER INTERACTION CAPABILITIES                     │
└─────────────────────────────────────────────────────────────────────┘

KNOWLEDGE BASE OPERATIONS
├── Add: "Add this paper/URL/concept to my research"
├── Remove: "Remove this source, it's not relevant"
├── Edit: "Update the notes for this finding"
├── Browse: "Show me all sources about topic X"
├── Search: "Find items related to machine learning"
└── Export: "Export this subset as BibTeX"

RESEARCH OPERATIONS
├── Expand: "Research more about sub-topic Y"
├── Question: "What does my research say about Z?"
├── Summarize: "Summarize the key findings so far"
├── Gaps: "What topics need more research?"
└── Contradict: "Are there conflicting views on X?"

AI STATE OPERATIONS
├── Plan: "Show me the current research plan"
├── Status: "What has been completed? What's pending?"
├── Reasoning: "Why did you conclude X?"
└── Reset: "Start fresh with a new direction"

DOCUMENT GENERATION (Optional)
├── Blog: "Generate a blog post from this research"
├── Paper: "Create an academic paper outline"
├── Summary: "Write an executive summary"
└── Custom: "Generate a document with these sections..."
```

---

## Research Methodology

When conducting research, the AI follows a structured approach (but always pausable/resumable):

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RESEARCH METHODOLOGY                            │
└─────────────────────────────────────────────────────────────────────┘

Step 1: TOPIC UNDERSTANDING
├── Input: User's research topic or question
├── Action: Clarify scope, identify key concepts
├── User Interaction: Confirm or refine direction
└── Output: Well-defined research question, sub-questions

Step 2: LITERATURE COLLECTION
├── Search: Query academic APIs (arXiv, PubMed, Semantic Scholar)
├── Retrieve: Download papers, parse PDFs with GROBID
├── Extract: NLP to extract abstracts, methods, results, citations
├── Store: Add all sources to knowledge base
└── User Interaction: User can pause, add sources, remove irrelevant items

Step 3: KNOWLEDGE SYNTHESIS
├── Analyze: Topic modeling, relation extraction for patterns
├── Build: Create knowledge graph of concepts and relationships
├── Identify: Find gaps, contradictions, key themes
├── Store: Persist synthesis in AI state
└── User Interaction: User can query, challenge, or redirect

Step 4: OPTIONAL - HYPOTHESIS GENERATION
├── Generate: LLM/rule-based reasoning to propose hypotheses
├── Prioritize: Rank by novelty, plausibility, feasibility
├── Store: Add hypotheses to knowledge base
└── User Interaction: User can accept, reject, or modify hypotheses

Step 5: OPTIONAL - DOCUMENT GENERATION
├── Select: User chooses output format and scope
├── Draft: AI synthesizes knowledge into document
├── Cite: Insert citations from knowledge base
├── Iterate: User provides feedback, AI revises
└── Output: Final document in chosen format
```

---

## Architecture

### Directory Structure

```
app/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py       # Main coordinator (LangGraph state machine)
│   ├── planner.py            # Decomposes query into sub-questions
│   ├── search_agent.py       # Web search subagent
│   ├── synthesis_agent.py    # Combines findings into document
│   ├── citation_agent.py     # Formats and validates citations
│   ├── hypothesis_agent.py   # Generates and ranks hypotheses
│   └── analysis_agent.py     # Performs statistical/ML analysis
├── tools/
│   ├── __init__.py
│   ├── web_search.py         # Tavily/DuckDuckGo search
│   ├── web_scraper.py        # Extract content from URLs
│   ├── arxiv_search.py       # Academic paper search
│   ├── wikipedia.py          # Wikipedia lookup
│   ├── pubmed_search.py      # PubMed medical literature
│   ├── semantic_scholar.py   # Semantic Scholar API
│   ├── pdf_parser.py         # GROBID/pdfplumber parsing
│   └── data_analysis.py      # Statistical analysis tools
├── nlp/
│   ├── __init__.py
│   ├── entity_extractor.py   # Named entity recognition
│   ├── relation_extractor.py # Relationship extraction
│   ├── summarizer.py         # Document summarization
│   └── topic_modeler.py      # Topic modeling (LDA)
├── knowledge/
│   ├── __init__.py
│   ├── graph_builder.py      # Knowledge graph construction
│   ├── graph_store.py        # Neo4j/RDFlib interface
│   └── vector_store.py       # Chroma/FAISS for RAG
├── memory/
│   ├── __init__.py
│   ├── research_state.py     # Pydantic state models
│   └── checkpointer.py       # PostgreSQL persistence
├── output/
│   ├── __init__.py
│   ├── document_builder.py   # Markdown generation
│   ├── citation_formatter.py # APA, MLA, Chicago styles
│   └── pdf_exporter.py       # PDF generation with Pandoc
└── analysis/
    ├── __init__.py
    ├── statistics.py         # Statistical tests (scipy)
    ├── ml_models.py          # sklearn/torch models
    └── visualization.py      # Matplotlib/Plotly charts
```

### Core Components

#### 1. Research State (Memory)

```python
class Citation(BaseModel):
    id: str                    # e.g., "[1]"
    url: str
    title: str
    author: Optional[str]
    date_accessed: str
    snippet: str               # Relevant excerpt
    source_type: SourceType    # web|arxiv|wikipedia|pubmed|semantic_scholar

class Entity(BaseModel):
    name: str
    type: str                  # concept|method|result|author|institution
    mentions: List[str]        # Citation IDs where mentioned

class Relationship(BaseModel):
    source: str                # Entity name
    target: str                # Entity name
    relation_type: str         # e.g., "causes", "correlates_with", "contradicts"
    evidence: List[str]        # Citation IDs supporting this relationship

class Hypothesis(BaseModel):
    id: str
    statement: str             # The hypothesis text
    supporting_evidence: List[str]  # Citation IDs
    contradicting_evidence: List[str]
    novelty_score: float       # 0-1, based on literature gap
    testability_score: float   # 0-1, based on data availability
    status: str                # proposed|testing|supported|refuted

class ExperimentResult(BaseModel):
    hypothesis_id: str
    method: str                # Statistical test or ML model used
    result_summary: str
    p_value: Optional[float]
    effect_size: Optional[float]
    figures: List[str]         # Paths to generated visualizations
    interpretation: str

class ResearchState(BaseModel):
    research_id: int
    query: str
    refined_question: Optional[str] = None  # Clarified research question
    sub_queries: List[str] = []             # Decomposed questions
    citations: List[Citation] = []          # Collected sources (knowledge base)
    entities: List[Entity] = []             # Extracted entities
    relationships: List[Relationship] = []  # Knowledge graph edges
    findings: dict[str, str] = {}           # sub_query -> finding
    hypotheses: List[Hypothesis] = []       # Generated hypotheses
    experiment_results: List[ExperimentResult] = []
    outline: Optional[str] = None           # Document structure
    draft: Optional[str] = None             # Current document
    conversation_history: List[dict] = []   # User-AI interaction history
    ai_reasoning: List[dict] = []           # AI decision log for transparency
    user_notes: dict[str, str] = {}         # User annotations on items
    status: str = "idle"                    # idle|researching|awaiting_input|generating
    errors: List[str] = []

class ConversationMessage(BaseModel):
    role: str                  # user|assistant|system
    content: str
    timestamp: str
    action_taken: Optional[str] = None  # What action resulted from this message
```

#### 2. LangGraph Orchestrator (Interactive State Machine)

The orchestrator is designed as an interactive state machine that responds to user commands
rather than running as a linear pipeline. The AI can pause at any point and wait for user input.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INTERACTIVE STATE MACHINE                        │
└─────────────────────────────────────────────────────────────────────┘

                              ┌───────────┐
                              │   IDLE    │◄───────────────────────┐
                              │ (waiting) │                        │
                              └─────┬─────┘                        │
                                    │ User input                   │
                                    ▼                              │
                        ┌───────────────────────┐                  │
                        │   ROUTE USER INTENT   │                  │
                        │   (classify action)   │                  │
                        └───────────┬───────────┘                  │
                                    │                              │
       ┌────────────────────────────┼────────────────────────────┐ │
       │                            │                            │ │
       ▼                            ▼                            ▼ │
┌──────────────┐          ┌─────────────────┐          ┌────────────────┐
│   RESEARCH   │          │  KNOWLEDGE BASE │          │   GENERATE     │
│   COMMANDS   │          │    COMMANDS     │          │   DOCUMENT     │
└──────┬───────┘          └────────┬────────┘          └───────┬────────┘
       │                           │                           │
       ▼                           ▼                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LAYER                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  RESEARCH:              KB MANAGEMENT:           DOC GENERATION:     │
│  ├─ plan_research       ├─ add_item              ├─ generate_blog    │
│  ├─ search_sources      ├─ remove_item           ├─ generate_paper   │
│  ├─ expand_topic        ├─ edit_item             ├─ generate_summary │
│  ├─ answer_question     ├─ browse_items          └─ iterate_draft    │
│  └─ find_gaps           ├─ search_kb                                 │
│                         └─ export_citations                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                         ┌────────────────────┐
                         │   UPDATE STATE     │
                         │   & PERSIST        │
                         └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │  RESPOND TO USER   │───────────────────────┘
                         └────────────────────┘

```

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

```sql
-- Existing table (extended)
ALTER TABLE research ADD COLUMN state_json JSONB;

-- Sources and citations
CREATE TABLE research_sources (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    url VARCHAR(2000),
    title VARCHAR(500),
    author VARCHAR(200),
    content_snippet TEXT,
    source_type VARCHAR(50),
    accessed_at TIMESTAMP WITH TIME ZONE
);

-- Checkpoints for LangGraph
CREATE TABLE research_checkpoints (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    thread_id VARCHAR(100),
    checkpoint_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE
);

-- Knowledge graph entities
CREATE TABLE research_entities (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    name VARCHAR(500),
    entity_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE
);

-- Knowledge graph relationships
CREATE TABLE research_relationships (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    source_entity_id INTEGER REFERENCES research_entities(id),
    target_entity_id INTEGER REFERENCES research_entities(id),
    relation_type VARCHAR(100),
    confidence FLOAT,
    evidence_source_ids INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE
);

-- Hypotheses
CREATE TABLE research_hypotheses (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    statement TEXT,
    supporting_evidence JSONB,
    contradicting_evidence JSONB,
    novelty_score FLOAT,
    testability_score FLOAT,
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Experiment results
CREATE TABLE research_experiments (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    hypothesis_id INTEGER REFERENCES research_hypotheses(id),
    method VARCHAR(200),
    parameters JSONB,
    result_summary TEXT,
    p_value FLOAT,
    effect_size FLOAT,
    figures JSONB,
    interpretation TEXT,
    created_at TIMESTAMP WITH TIME ZONE
);

-- Vector embeddings for RAG
CREATE TABLE research_embeddings (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    source_id INTEGER REFERENCES research_sources(id),
    chunk_text TEXT,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE
);
```

---

## Implementation Phases

Implementation is organized in phases, building progressively from foundation to advanced capabilities. Each phase depends on previous phases being complete.

### Phase 1: Foundation ✅ Priority: HIGH
- [x] Add new dependencies to `requirements.txt`
- [x] Create `app/memory/research_state.py` with Pydantic models
- [x] Create `app/models.py` additions for sources and checkpoints
- [ ] Set up database migrations

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
- [ ] PDF export with Pandoc

---

### Phase 7: Interactive Knowledge Base API | Priority: HIGH ⭐ NEW
*Enable user interaction with the knowledge base through conversational API*

- [ ] Implement `/research/{id}/chat` endpoint (main interaction)
  - Intent classification (research, add, remove, question, generate)
  - Route to appropriate handler based on intent
  - Return structured response with action taken
- [ ] Implement conversation history storage
  - Store messages in database
  - GET `/research/{id}/chat/history` endpoint
- [ ] Implement Knowledge Base CRUD endpoints
  - POST `/research/{id}/sources` - add source manually
  - PATCH `/research/{id}/sources/{id}` - update notes/tags
  - DELETE `/research/{id}/sources/{id}` - remove source
  - GET `/research/{id}/sources` with filtering/search
- [ ] Implement findings management endpoints
  - CRUD for user-created findings
  - Link findings to sources
- [ ] Implement AI state transparency endpoints
  - GET `/research/{id}/state` - current AI state
  - GET `/research/{id}/plan` - research plan with progress
  - PATCH `/research/{id}/plan` - modify plan
- [ ] Update `ResearchState` model with conversation and reasoning fields
- [ ] Implement intent router agent using LLM classification
- [ ] Add response formatter for consistent API responses

### Phase 8: Extended Search Tools | Priority: HIGH
*Expand search capabilities to more academic sources*

- [x] Implement `app/tools/pubmed_search.py` - PubMed/MEDLINE API
- [x] Implement `app/tools/semantic_scholar.py` - Semantic Scholar API
- [ ] Implement `app/tools/crossref_search.py` - Crossref DOI/metadata
- [ ] Implement `app/tools/openalex_search.py` - OpenAlex open scholarly data
- [ ] Add PDF download and caching for full-text retrieval

### Phase 9: PDF & Document Parsing | Priority: HIGH
*Extract structured content from academic PDFs*

- [ ] Set up GROBID service (Docker container)
- [ ] Implement `app/tools/pdf_parser.py` using GROBID
- [ ] Add fallback parsing with `pdfplumber`/`PyPDF2`
- [ ] Extract figures, tables, and equations
- [ ] Implement BibTeX parsing with `bibtexparser`
- [ ] Create document chunking for large papers

### Phase 10: NLP & Knowledge Extraction | Priority: HIGH
*Extract structured knowledge from text*

- [ ] Create `app/nlp/` module structure
- [ ] Implement `app/nlp/entity_extractor.py` using spaCy
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

### Phase 12: Hypothesis Generation | Priority: MEDIUM (Optional)
*Identify gaps and propose hypotheses - can be skipped if not needed*

- [ ] Implement `app/agents/hypothesis_agent.py`
  - Analyze knowledge graph for gaps (missing relationships)
  - Identify contradictions in literature
  - Propose testable hypotheses using LLM reasoning
- [ ] Add hypothesis ranking system
  - Novelty score (inverse of existing evidence)
  - Plausibility score (consistency with known relationships)
  - Testability score (data availability)
- [ ] Implement hypothesis validation against existing literature
- [ ] Add user feedback loop for hypothesis refinement
- [ ] Update orchestrator with hypothesis generation step

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

- [ ] Add WebSocket endpoint for progress updates
- [ ] Stream partial results as research progresses
- [ ] Add research cancellation endpoint
- [ ] Implement research resumption from checkpoints
- [ ] Add batch research submission
- [ ] Rate limiting and usage quotas

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

---

## Dependencies

### Currently Installed (Phases 1-6)
```
langgraph>=0.2.0
tavily-python>=0.3.0
duckduckgo-search>=5.0
arxiv>=2.1.0
wikipedia>=1.4.0
beautifulsoup4>=4.12.0
trafilatura>=1.6.0
```

### Phase 7: Extended Search
```
biopython>=1.83            # PubMed/NCBI access
semanticscholar>=0.7.0     # Semantic Scholar API
crossrefapi>=1.5.0         # Crossref metadata
pyalex>=0.13               # OpenAlex API
```

### Phase 8: PDF Parsing
```
grobid-client-python>=0.0.7  # GROBID integration
pdfplumber>=0.10.0           # PDF text extraction
PyPDF2>=3.0.0                # PDF manipulation
bibtexparser>=1.4.0          # BibTeX parsing
```

### Phase 9: NLP & Knowledge Extraction
```
spacy>=3.7.0                 # NLP pipeline
en_core_sci_lg               # Scientific NER model (scispaCy)
transformers>=4.35.0         # Summarization models
torch>=2.1.0                 # PyTorch backend
gensim>=4.3.0                # Topic modeling
bertopic>=0.15.0             # Neural topic modeling (optional)
```

### Phase 10: Knowledge Graph & Storage
```
neo4j>=5.14.0                # Neo4j driver
rdflib>=7.0.0                # RDF/knowledge graphs
chromadb>=0.4.0              # Vector store
sentence-transformers>=2.2.0 # Embeddings
faiss-cpu>=1.7.4             # Fast similarity search (optional)
elasticsearch>=8.11.0        # Full-text search (optional)
```

### Phase 12-13: Analysis
```
scipy>=1.11.0                # Statistical tests
statsmodels>=0.14.0          # Regression analysis
scikit-learn>=1.3.0          # ML algorithms
dowhy>=0.11.0                # Causal inference
matplotlib>=3.8.0            # Static visualization
plotly>=5.18.0               # Interactive charts
seaborn>=0.13.0              # Statistical visualization
```

### Phase 14: Report Generation
```
pandoc                       # System package (not pip)
pypandoc>=1.12               # Python Pandoc wrapper
jinja2>=3.1.0                # Template rendering
weasyprint>=60.0             # HTML to PDF (alternative)
```

### Phase 16: Workflow (Optional)
```
prefect>=2.14.0              # Workflow orchestration
apache-airflow>=2.8.0        # Alternative orchestration
```

---

## API Design

### Core API Philosophy

The API is designed around the interactive research assistant model:
- **Conversational**: Main interaction through a chat-like endpoint
- **Knowledge Base CRUD**: Full control over research items
- **State Transparency**: Users can inspect AI reasoning and state
- **Document Generation**: Optional output generation from accumulated knowledge

### Research Session Endpoints

```
# Session Management
POST /research
  - Accepts: { topic: string, description?: string }
  - Returns: { id, status: "idle", created_at }
  - Creates a new research session (knowledge base)

GET /research
  - Returns: list of all research sessions
  - Supports pagination and filtering

GET /research/{id}
  - Returns: full research state including KB stats, AI state

DELETE /research/{id}
  - Deletes research session and all associated data
```

### Conversation / Chat Endpoint (Primary Interface)

```
POST /research/{id}/chat
  - Accepts: { message: string }
  - Returns: { 
      response: string,           # AI's response
      action_taken: string,       # add|remove|search|generate|etc
      state_changes: object,      # What changed in the KB/state
      suggestions?: string[]      # Optional follow-up suggestions
    }
  - This is the main interaction point - handles all user intents
  - AI routes to appropriate action based on intent classification

GET /research/{id}/chat/history
  - Returns: list of conversation messages with timestamps
  - Supports pagination
```

### Knowledge Base Endpoints

```
# Sources / Citations
GET /research/{id}/sources
  - Returns: list of all sources in KB
  - Supports filtering: ?type=arxiv&search=keyword

POST /research/{id}/sources
  - Accepts: { url?: string, doi?: string, manual?: object }
  - Returns: { source_id, parsed_data }
  - Manually add a source to the KB

GET /research/{id}/sources/{source_id}
  - Returns: full source details including extracted content

PATCH /research/{id}/sources/{source_id}
  - Accepts: { notes?: string, tags?: string[], relevant?: boolean }
  - Updates user annotations on a source

DELETE /research/{id}/sources/{source_id}
  - Removes source from KB

# Findings
GET /research/{id}/findings
  - Returns: list of synthesized findings
  - Each finding links to supporting sources

POST /research/{id}/findings
  - Accepts: { content: string, source_ids?: string[] }
  - Manually add a finding

PATCH /research/{id}/findings/{finding_id}
  - Update finding content or linked sources

DELETE /research/{id}/findings/{finding_id}
  - Remove finding

# Entities & Relationships (Knowledge Graph)
GET /research/{id}/entities
  - Returns: list of extracted entities with metadata

GET /research/{id}/relationships
  - Returns: list of relationships between entities

GET /research/{id}/graph
  - Returns: { nodes: [], edges: [] } for visualization
```

### AI State Endpoints

```
GET /research/{id}/state
  - Returns: {
      status: "idle"|"researching"|"awaiting_input"|"generating",
      current_plan: object,       # Research plan breakdown
      pending_queries: string[],  # Queries not yet researched
      reasoning_log: object[],    # AI decision history
      last_activity: timestamp
    }

GET /research/{id}/plan
  - Returns: current research plan with sub-queries and progress

PATCH /research/{id}/plan
  - Accepts: { add_queries?: string[], remove_queries?: string[] }
  - Modify the research plan

POST /research/{id}/reset
  - Resets AI state while preserving KB (start fresh direction)
```

### Document Generation Endpoints

```
POST /research/{id}/generate
  - Accepts: { 
      format: "blog"|"paper"|"summary"|"custom",
      options?: {
        sections?: string[],       # For custom format
        citation_style?: "apa"|"mla"|"chicago",
        include_sources?: string[] # Subset of KB to use
      }
    }
  - Returns: { draft_id, status: "generating" }
  - Triggers async document generation

GET /research/{id}/drafts
  - Returns: list of generated drafts

GET /research/{id}/drafts/{draft_id}
  - Returns: { content, format, citations, created_at }

POST /research/{id}/drafts/{draft_id}/iterate
  - Accepts: { feedback: string }
  - Returns: { updated_content }
  - Iterate on draft with user feedback

GET /research/{id}/drafts/{draft_id}/export
  - Query: ?format=md|pdf|html|docx
  - Returns: file download
```

### Export Endpoints

```
GET /research/{id}/export/bibtex
  - Returns: BibTeX file of all sources

GET /research/{id}/export/json
  - Returns: full KB as JSON (for backup/migration)

POST /research/{id}/import
  - Accepts: JSON or BibTeX file
  - Imports sources into KB
```

### (Future) Real-time Endpoints

```
WS /research/{id}/stream
  - Streams: { event_type, data, timestamp }
  - Events: 
    - source_added, source_removed
    - finding_created
    - research_progress
    - generation_progress
  - Low priority - for future UI integration
```

---

## Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=              # OpenAI API key
LLM_PROVIDER=openai          # openai|ollama
LLM_MODEL=gpt-4o             # Model to use

# Search APIs
TAVILY_API_KEY=              # Required for web search
SEMANTIC_SCHOLAR_API_KEY=    # Optional, higher rate limits
NCBI_API_KEY=                # Optional, for PubMed

# Database
DATABASE_URL=                # PostgreSQL connection string
NEO4J_URI=                   # Neo4j connection (Phase 10)
NEO4J_USER=                  # Neo4j username
NEO4J_PASSWORD=              # Neo4j password
ELASTICSEARCH_URL=           # Elasticsearch (optional)

# Vector Store
CHROMA_PERSIST_DIR=          # Chroma persistence directory
EMBEDDING_MODEL=             # text-embedding-ada-002 or local model

# Research Limits
RESEARCH_MAX_SOURCES=20      # Max citations per research
RESEARCH_TIMEOUT=300         # Max seconds per research
MAX_PDF_SIZE_MB=50           # Max PDF file size to parse
MAX_CONCURRENT_SEARCHES=5    # Rate limiting

# Services (Docker)
GROBID_URL=                  # GROBID service URL
```

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
```yaml
services:
  grobid:
    image: lfoppiano/grobid:0.8.0
    ports:
      - "8070:8070"
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"
      - "7687:7687"
  elasticsearch:
    image: elasticsearch:8.11.3
    ports:
      - "9200:9200"
```
