# End-to-End Testing

## Overview

The e2e test (`tests/e2e_test.py`) provides comprehensive testing of the LLM Researcher system, covering all major API endpoints and workflows.

## Running the Test

```bash
make e2e
```

Or directly:
```bash
docker compose exec app python tests/e2e_test.py
```

## What the Test Covers

The e2e test executes 20 test steps covering:

### Core Research Operations
- ✅ Create research project
- ✅ List research projects
- ✅ Get research details
- ✅ Trigger research via chat
- ✅ Wait for sources to be collected
- ✅ Get full research document

### Source Management
- ✅ Get sources with filtering (by type, tag, search)
- ✅ Manually add a source
- ✅ Update source notes and tags
- ✅ Search sources by keyword
- ✅ Filter sources by tag

### Findings Management
- ✅ Create research findings
- ✅ List findings
- ✅ Update finding content
- ✅ Link findings to sources

### AI State Transparency
- ✅ Get research state (status, counts, pending/completed queries)
- ✅ Get research plan (sub-queries, progress)
- ✅ Update research plan (add/remove queries, refine question)

### Conversational Interface
- ✅ Chat with research assistant
- ✅ Get chat history
- ✅ Status checks via chat
- ✅ Browse sources via chat

## Test Flow

1. **Setup**: Wait for API to be ready
2. **Research Creation**: Create a new research project
3. **Research Execution**: Trigger research via chat (background task)
4. **Manual Operations**: Add sources and findings manually
5. **State Management**: Test state and plan endpoints
6. **Verification**: Verify all CRUD operations and filters work
7. **Summary**: Display test results

## Expected Behavior

- All 20 test steps should pass
- The test creates real data in the database
- Background research may take time to complete (test waits up to 90s)
- If background research doesn't complete, test continues with manual source addition
- Test is idempotent and can be run multiple times

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

## Notes

- Requires the app to be running (`make up` or `make dev`)
- Creates test data in the database (research project with ID)
- Does not automatically clean up test data
- Safe to run multiple times (creates new research projects each time)
