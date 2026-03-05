# Query Expansion Feature

## Overview

The query expansion feature automatically generates multiple variations of each search query to improve search coverage and find more relevant sources. Instead of searching with a single phrasing, the system now creates 2-3 alternative formulations using synonyms, related terms, and different phrasings.

## How It Works

### 1. Query Variation Generation

When a sub-query is created by the planner, the search agent now:

1. Takes the original sub-query
2. Uses an LLM to generate 2-3 alternative phrasings
3. Searches with all variations (original + alternatives)
4. Merges and deduplicates the results

### 2. Example

**Original Query:** "What are the health benefits of meditation?"

**Generated Variations:**
- "meditation positive effects wellbeing health"
- "mindfulness practice health advantages benefits"  
- "how does meditation improve physical mental health"

The system searches with all 4 queries (original + 3 variations), then combines the results while removing duplicates.

### 3. Duplicate Handling

Results are deduplicated by URL before relevance filtering, ensuring:
- No duplicate sources in the final results
- Maximum unique coverage across different phrasings
- Efficient use of the research source limit

### 4. Relevance Filtering

After collecting results from all variations, citations are filtered for relevance against the **original** sub-query, ensuring all results are truly relevant to the research question.

## Configuration

Control query expansion via environment variables or [config.py](../app/config.py):

```python
# Enable/disable query expansion
research_enable_query_expansion: bool = True

# Number of variations to generate (default: 2)
# Total queries = 1 original + N variations
research_query_variations: int = 2
```

## Performance Considerations

- **Search Time**: Increases proportionally to number of variations (e.g., 3x queries = ~3x search time)
- **Result Quality**: Significantly improved coverage, especially for:
  - Technical topics with multiple terminologies
  - Concepts with formal/informal language variations
  - Queries where exact phrasing matters
  
- **API Costs**: More search API calls (Tavily, ArXiv, etc.)

## Disabling Query Expansion

To disable and use only the original query:

```bash
# In .env file
RESEARCH_ENABLE_QUERY_EXPANSION=false
```

Or set `research_enable_query_expansion = False` in [config.py](../app/config.py).

## Implementation Details

- **Module**: [app/agents/query_expander.py](../app/agents/query_expander.py)
- **Integration**: [app/agents/search_agent.py](../app/agents/search_agent.py) in `search_for_subquery()`
- **Tests**: [tests/test_agents.py](../tests/test_agents.py) in `TestQueryExpander`

## Benefits

1. **Improved Coverage**: Finds sources that use different terminology
2. **Better Results**: Captures formal/informal variations
3. **Robust Search**: Less sensitive to exact query phrasing
4. **Smart Deduplication**: Ensures unique sources across all variations
5. **Flexible**: Can be easily enabled/disabled via configuration

## Future Enhancements

Potential improvements:
- Dynamic variation count based on query complexity
- Domain-specific expansion strategies (academic vs. general)
- Learning from successful variation patterns
- Cache query variations to reduce LLM calls
