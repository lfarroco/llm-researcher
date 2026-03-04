# LLM Researcher - Architecture Plan

## Overview

An autonomous research agent that can search for information online about a given topic, collect sources with proper citations, and produce a well-structured research document.

## Goals

1. **Web Research**: Search multiple sources (web, academic papers, Wikipedia) for relevant information
2. **Citation Management**: Track all sources and generate proper citations in the final document
3. **Parallel Execution**: Multiple subagents work concurrently on different aspects of the research
4. **Persistent Memory**: Save research state to allow resumption and track progress
5. **Structured Output**: Generate documents with inline citations and a references section

---

## Architecture

### Directory Structure

```
app/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py      # Main coordinator (LangGraph state machine)
│   ├── planner.py           # Decomposes query into sub-questions
│   ├── search_agent.py      # Web search subagent
│   ├── synthesis_agent.py   # Combines findings into document
│   └── citation_agent.py    # Formats and validates citations
├── tools/
│   ├── __init__.py
│   ├── web_search.py        # Tavily/DuckDuckGo search
│   ├── web_scraper.py       # Extract content from URLs
│   ├── arxiv_search.py      # Academic paper search
│   └── wikipedia.py         # Wikipedia lookup
├── memory/
│   ├── __init__.py
│   ├── research_state.py    # Pydantic state models
│   └── checkpointer.py      # PostgreSQL persistence
├── output/
│   ├── __init__.py
│   ├── document_builder.py  # Markdown generation
│   └── citation_formatter.py # APA, MLA, Chicago styles
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
    source_type: SourceType    # web|arxiv|wikipedia

class ResearchState(BaseModel):
    research_id: int
    query: str
    sub_queries: List[str] = []           # Decomposed questions
    citations: List[Citation] = []         # Collected sources
    findings: dict[str, str] = {}          # sub_query -> finding
    outline: Optional[str] = None          # Document structure
    draft: Optional[str] = None            # Current document
    status: str = "planning"               # planning|searching|synthesizing|complete
    errors: List[str] = []
```

#### 2. LangGraph Orchestrator

```
┌─────────────┐
│   PLANNER   │  Decompose query into sub-questions
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   SEARCH    │  Parallel search for each sub-query
│  (parallel) │  - Web search (Tavily)
│             │  - ArXiv (if academic)
│             │  - Wikipedia (for context)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ SYNTHESIZE  │  Combine findings into coherent narrative
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  CITATIONS  │  Format references, validate URLs
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   OUTPUT    │  Generate final document
└─────────────┘
```

#### 3. Tools

| Tool                      | Purpose                            | Package             |
|---------------------------|------------------------------------|---------------------|
| `TavilySearchResults`     | Web search with built-in citations | `tavily-python`     |
| `DuckDuckGoSearchResults` | Free fallback search               | `duckduckgo-search` |
| `ArxivQueryRun`           | Academic paper search              | `arxiv`             |
| `WikipediaQueryRun`       | Encyclopedia lookups               | `wikipedia`         |
| `WebScraper`              | Extract full page content          | `trafilatura`       |

#### 4. Database Schema

```sql
-- Existing table (extended)
ALTER TABLE research ADD COLUMN state_json JSONB;

-- New tables
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

CREATE TABLE research_checkpoints (
    id SERIAL PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    thread_id VARCHAR(100),
    checkpoint_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE
);
```

---

## Implementation Phases

### Phase 1: Foundation ✅ Priority: HIGH
- [ ] Add new dependencies to `requirements.txt`
- [ ] Create `app/memory/research_state.py` with Pydantic models
- [ ] Create `app/models.py` additions for sources and checkpoints
- [ ] Set up database migrations

### Phase 2: Tools ✅ Priority: HIGH
- [ ] Implement `app/tools/web_search.py` (Tavily + DuckDuckGo fallback)
- [ ] Implement `app/tools/arxiv_search.py`
- [ ] Implement `app/tools/wikipedia.py`
- [ ] Implement `app/tools/web_scraper.py`

### Phase 3: Agents ✅ Priority: HIGH
- [ ] Implement `app/agents/planner.py` - query decomposition
- [ ] Implement `app/agents/search_agent.py` - tool-calling agent
- [ ] Implement `app/agents/synthesis_agent.py` - document drafting
- [ ] Implement `app/agents/orchestrator.py` - LangGraph workflow

### Phase 4: Parallel Execution ✅ Priority: MEDIUM
- [ ] Add async support to search agent
- [ ] Implement `asyncio.gather` for concurrent sub-query searches
- [ ] Add rate limiting and error handling

### Phase 5: Citations ✅ Priority: MEDIUM
- [ ] Implement citation extraction from search results
- [ ] Implement `app/output/citation_formatter.py` (APA, MLA, Chicago)
- [ ] Add citation validation (check URLs are accessible)

### Phase 6: Output Generation ✅ Priority: MEDIUM
- [ ] Implement `app/output/document_builder.py`
- [ ] Add inline citation markers `[1]`, `[2]` in text
- [ ] Generate references section
- [ ] Optional: PDF export

### Phase 7: API & Streaming ✅ Priority: LOW
- [ ] Add WebSocket endpoint for progress updates
- [ ] Stream partial results as research progresses
- [ ] Add research cancellation endpoint

---

## Dependencies to Add

```
# requirements.txt additions
langgraph>=0.2.0
tavily-python>=0.3.0
duckduckgo-search>=5.0
arxiv>=2.1.0
wikipedia>=1.4.0
beautifulsoup4>=4.12.0
trafilatura>=1.6.0
```

---

## API Changes

### New Endpoints

```
POST /research
  - Accepts: { query: string, depth: "quick"|"standard"|"deep" }
  - Returns: { id, status: "planning" }

GET /research/{id}/stream
  - WebSocket: streams progress updates
  - Messages: { phase, progress, current_task, findings_count }

GET /research/{id}/sources
  - Returns: list of all citations collected

GET /research/{id}/document
  - Returns: { markdown, pdf_url?, citations }
```

---

## Environment Variables

```
TAVILY_API_KEY=          # Required for web search
OPENAI_API_KEY=          # Or use Ollama
LLM_PROVIDER=openai      # openai|ollama
LLM_MODEL=gpt-4o         # Model to use
RESEARCH_MAX_SOURCES=20  # Max citations per research
RESEARCH_TIMEOUT=300     # Max seconds per research
```

---

## Notes

- **LangGraph** is used for the multi-step workflow with checkpointing
- **Tavily** is preferred for web search as it returns structured citations
- State is persisted to PostgreSQL via LangGraph's `PostgresSaver`
- All searches run in parallel using `asyncio.gather`
- Citations follow a consistent format with URL, title, date accessed
