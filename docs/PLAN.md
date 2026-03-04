# LLM Researcher - Architecture Plan

## Overview

An autonomous AI research agent that emulates the scientific method to assist researchers in collecting information and discovering new knowledge. The agent searches multiple sources, builds knowledge graphs, generates hypotheses, performs analyses, and produces well-structured research documents with proper citations.

## Goals

1. **Scientific Method Workflow**: Follow a structured process (question → literature review → hypothesis → experiment → analysis → report)
2. **Web Research**: Search multiple sources (web, academic papers, Wikipedia, PubMed) for relevant information
3. **Knowledge Extraction**: Use NLP to extract entities, relationships, and insights from literature
4. **Knowledge Representation**: Build knowledge graphs linking papers, concepts, and findings
5. **Hypothesis Generation**: Identify gaps and propose testable hypotheses from literature analysis
6. **Data Analysis**: Perform statistical tests and ML-based pattern discovery
7. **Citation Management**: Track all sources and generate proper citations in the final document
8. **Parallel Execution**: Multiple subagents work concurrently on different aspects of the research
9. **Persistent Memory**: Save research state to allow resumption and track progress
10. **Structured Output**: Generate documents with inline citations and a references section

---

## Scientific Method Workflow

The agent follows the scientific method in a structured, iterative workflow:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SCIENTIFIC METHOD WORKFLOW                       │
└─────────────────────────────────────────────────────────────────────┘

Step 1: DEFINE RESEARCH QUESTION
├── Input: Broad topic or specific query
├── Action: NLP to clarify and refine (identify key concepts, scope)
└── Output: Well-defined research question (PICO format, sub-questions)

Step 2: LITERATURE REVIEW
├── Search: Query academic APIs (arXiv, PubMed, Semantic Scholar)
├── Retrieve: Download papers, parse PDFs with GROBID
├── Extract: NLP to extract abstracts, methods, results, citations
├── Synthesize: Build knowledge graph, identify gaps
└── Output: Literature review section, state of the art summary

Step 3: FORMULATE HYPOTHESES
├── Analyze: Topic modeling, relation extraction for patterns
├── Generate: LLM/rule-based reasoning to propose hypotheses
├── Prioritize: Rank by novelty, plausibility, feasibility
└── Output: List of testable hypotheses with supporting evidence

Step 4: DESIGN EXPERIMENTS
├── Data Needs: Determine required datasets
├── Method Selection: Choose statistical tests, ML models
├── Protocol: Define setup, variables, controls, metrics
└── Output: Detailed methods section

Step 5: EXECUTE EXPERIMENTS
├── Data Collection: APIs, web scraping, simulations
├── Analysis: Statistical tests, train models, run simulations
├── Visualization: Generate plots and tables
└── Output: Raw results, figures, intermediate data

Step 6: INTERPRET RESULTS
├── Compare: Check if results support/refute hypotheses
├── Contextualize: Relate findings to literature
├── Refine: If inconclusive, iterate steps 4-6
└── Output: Discussion section with interpretation

Step 7: GENERATE REPORT
├── Structure: Title, Abstract, Introduction, Methods, Results, etc.
├── Write: LLM-assisted drafting grounded in data
├── Cite: Insert citations from knowledge graph
├── Format: Convert to PDF/HTML/Markdown
└── Output: Complete research report

Step 8: ITERATE & IMPROVE
├── Feedback: User refinements
├── Update: Re-run as new papers/data become available
└── Version: Git tracking for reproducibility
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
    refined_question: Optional[str] = None  # PICO-formatted question
    sub_queries: List[str] = []             # Decomposed questions
    citations: List[Citation] = []          # Collected sources
    entities: List[Entity] = []             # Extracted entities
    relationships: List[Relationship] = []  # Knowledge graph edges
    findings: dict[str, str] = {}           # sub_query -> finding
    hypotheses: List[Hypothesis] = []       # Generated hypotheses
    experiment_results: List[ExperimentResult] = []
    outline: Optional[str] = None           # Document structure
    draft: Optional[str] = None             # Current document
    status: str = "planning"                # planning|reviewing|hypothesizing|experimenting|synthesizing|complete
    errors: List[str] = []
```

#### 2. LangGraph Orchestrator

```
┌──────────────────┐
│  QUESTION REFINE │  Clarify and scope the research question
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│     PLANNER      │  Decompose query into sub-questions
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│     SEARCH       │  Parallel search for each sub-query
│    (parallel)    │  - Web search (Tavily)
│                  │  - ArXiv (academic papers)
│                  │  - PubMed (medical literature)
│                  │  - Semantic Scholar (citations)
│                  │  - Wikipedia (context)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  NLP EXTRACTION  │  Extract entities, relationships, key findings
│    (parallel)    │  - Named Entity Recognition
│                  │  - Relation Extraction
│                  │  - Summarization
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ KNOWLEDGE GRAPH  │  Build graph of concepts and relationships
│                  │  - Store in Neo4j/vector DB
│                  │  - Identify patterns and gaps
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   HYPOTHESIS     │  Generate and rank hypotheses
│   GENERATION     │  - Identify literature gaps
│                  │  - Propose testable claims
│                  │  - Score by novelty/feasibility
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   EXPERIMENT     │  Design and execute analyses
│    DESIGN        │  - Select statistical methods
│                  │  - Define protocols
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    ANALYSIS      │  Run experiments and interpret
│                  │  - Statistical tests
│                  │  - ML pattern discovery
│                  │  - Generate visualizations
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   SYNTHESIZE     │  Combine findings into coherent narrative
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   CITATIONS      │  Format references, validate URLs
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│     OUTPUT       │  Generate final document (MD/PDF/HTML)
└──────────────────┘
```

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

### Phase 7: Extended Search Tools | Priority: HIGH
*Expand search capabilities to more academic sources*

- [x] Implement `app/tools/pubmed_search.py` - PubMed/MEDLINE API
- [x] Implement `app/tools/semantic_scholar.py` - Semantic Scholar API
- [ ] Implement `app/tools/crossref_search.py` - Crossref DOI/metadata
- [ ] Implement `app/tools/openalex_search.py` - OpenAlex open scholarly data
- [ ] Add PDF download and caching for full-text retrieval

### Phase 8: PDF & Document Parsing | Priority: HIGH
*Extract structured content from academic PDFs*

- [ ] Set up GROBID service (Docker container)
- [ ] Implement `app/tools/pdf_parser.py` using GROBID
- [ ] Add fallback parsing with `pdfplumber`/`PyPDF2`
- [ ] Extract figures, tables, and equations
- [ ] Implement BibTeX parsing with `bibtexparser`
- [ ] Create document chunking for large papers

### Phase 9: NLP & Knowledge Extraction | Priority: HIGH
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

### Phase 10: Knowledge Graph & Storage | Priority: HIGH
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

### Phase 11: Hypothesis Generation | Priority: MEDIUM
*Identify gaps and propose hypotheses*

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

### Phase 12: Experiment Design | Priority: MEDIUM
*Design analyses to test hypotheses*

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

### Phase 13: Data Analysis & Visualization | Priority: MEDIUM
*Execute experiments and visualize results*

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

### Phase 14: Advanced Report Generation | Priority: MEDIUM
*Generate publication-ready documents*

- [ ] Implement `app/output/document_builder.py` (full version)
  - Standard academic structure (Abstract, Introduction, Methods, etc.)
  - Section-aware content generation
  - Inline figure and table placement
- [ ] Implement `app/output/pdf_exporter.py`
  - Pandoc integration for format conversion
  - LaTeX templates for academic styling
  - HTML export with interactive elements
- [ ] Add automatic abstract generation
- [ ] Generate executive summary for non-technical audiences
- [ ] Support multiple citation styles (already have APA, MLA, Chicago)
- [ ] Version control for report drafts with Git integration

### Phase 15: API & Real-time Updates | Priority: LOW
*Enable real-time progress tracking and advanced API features*

- [ ] Add WebSocket endpoint for progress updates
- [ ] Stream partial results as research progresses
- [ ] Add research cancellation endpoint
- [ ] Implement research resumption from checkpoints
- [ ] Add batch research submission
- [ ] Rate limiting and usage quotas

### Phase 16: Workflow Orchestration | Priority: LOW
*Advanced workflow management for complex research*

- [ ] Consider Apache Airflow/Prefect for complex pipelines
- [ ] Implement scheduled re-runs for literature monitoring
- [ ] Add notification system for research completion
- [ ] Multi-research project management
- [ ] Collaboration features (multiple users per research)

### Phase 17: Quality & Reproducibility | Priority: LOW
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

## API Changes

### Current Endpoints

```
POST /research
  - Accepts: { query: string, depth: "quick"|"standard"|"deep" }
  - Returns: { id, status: "planning" }

GET /research/{id}
  - Returns: { id, query, status, draft, citations }

GET /research/{id}/sources
  - Returns: list of all citations collected

GET /research/{id}/document
  - Returns: { markdown, pdf_url?, citations }
```

### New Endpoints (Phases 7+)

```
# Knowledge Graph
GET /research/{id}/entities
  - Returns: list of extracted entities with metadata

GET /research/{id}/relationships
  - Returns: list of relationships between entities

GET /research/{id}/graph
  - Returns: { nodes: [], edges: [] } for visualization

# Hypotheses
GET /research/{id}/hypotheses
  - Returns: list of generated hypotheses with scores

POST /research/{id}/hypotheses/{hypothesis_id}/test
  - Triggers experimental analysis for a hypothesis
  - Returns: { experiment_id, status: "running" }

# Analysis
GET /research/{id}/experiments
  - Returns: list of experiment results

GET /research/{id}/experiments/{experiment_id}
  - Returns: detailed results with figures

GET /research/{id}/figures
  - Returns: list of generated visualizations

# Real-time (WebSocket)
WS /research/{id}/stream
  - Streams: { phase, progress, current_task, findings_count }
  - Events: entity_extracted, hypothesis_generated, experiment_complete

# Management
POST /research/{id}/cancel
  - Cancels running research

POST /research/{id}/resume
  - Resumes from last checkpoint

PATCH /research/{id}/hypotheses/{hypothesis_id}
  - Update hypothesis (user feedback/refinement)
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

### Future Architecture Considerations
- **Knowledge Graph**: Neo4j will store entities and relationships, enabling:
  - Literature gap detection (missing edges)
  - Contradiction identification (conflicting edges)
  - Citation network analysis
- **RAG Pipeline**: Chroma/FAISS vector store for semantic retrieval:
  - Chunk papers into embeddings
  - Retrieve relevant context for hypothesis generation
  - Ground LLM outputs in source material
- **GROBID**: Self-hosted service for PDF parsing:
  - Extracts structured sections from academic PDFs
  - Handles complex layouts with figures/tables
  - Returns TEI XML for consistent parsing
- **Reproducibility**: All research runs are versioned:
  - Git-tracked output documents
  - Docker environments for analysis code
  - Data snapshots for replication

### Recommended Implementation Order

1. **Phase 7 (Extended Search)** - More sources = better literature coverage
2. **Phase 8 (PDF Parsing)** - Access full paper content, not just abstracts
3. **Phase 9 (NLP Extraction)** - Foundation for knowledge graph
4. **Phase 10 (Knowledge Graph)** - Enable hypothesis generation
5. **Phase 11 (Hypothesis)** - Core scientific method capability
6. **Phases 12-13 (Analysis)** - Test hypotheses with data
7. **Phase 14 (Reports)** - Publication-quality output
8. **Phases 15-17** - Polish and scale

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
