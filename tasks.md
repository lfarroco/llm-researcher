# Tasks — High-Priority Issues

**Last updated**: 2026-08-13

High-priority issues found during LLM-driven end-to-end testing of the
research pipeline. The test kit used to reproduce them is documented in
[`docs/LLM_TESTING.md`](docs/LLM_TESTING.md); the general roadmap lives in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

Status legend:

- `[ ]` not started
- `[~]` in progress
- `[x]` fixed

---

## [P0] Completed research item can get stuck in `researching` status via chat

### Symptom

After a research item completes (`status=complete`), sending a chat message
that the intent router classifies as `research` — for example
*"Summarize the key challenges of citizen reporting in smart cities in 3
bullets."* was misclassified as `research` — flips the item to
`status=researching` and queues a re-run that never executes. The item stays in
`researching` indefinitely. Its document, sources, and findings remain intact,
but the status never returns to `complete`, and there is no API endpoint to
reset it.

### Steps to reproduce

1. Start the app (see `docs/LLM_TESTING.md`).
2. `POST /research` with any query and wait until `GET /research/{id}` returns
   `status=complete`.
3. `POST /research/{id}/chat` with
   `{"message": "Summarize the key challenges of citizen reporting in smart cities in 3 bullets."}`
4. `GET /research/{id}` now returns `status=researching` forever.

### Root cause

`app/services/chat_handlers.py::handle_research_intent` unconditionally sets
`research.status = "researching"` and queues
`app.services.research_service.process_research`, which only *claims* items
whose status is `pending` (see the `UPDATE ... WHERE status = 'pending'` claim
in `process_research_async`). Because the status was already changed to
`researching`, the re-run no-ops ("already claimed or not pending") and nothing
ever flips it back. `POST /research/{id}/resume` only accepts
`cancelled`/`error`/`failed`, so there is no recovery path.

### Impact

- Completed research items lose their terminal status.
- The frontend (which renders status) shows a false "researching" state.
- Agents and test harnesses polling for `complete` can hang until timeout.

### Suggested fix (pick one or more)

- **Preferred**: in `handle_research_intent`, if the item already has a
  terminal status (`complete`/`failed`/`error`), create a *new* `Research`
  row instead of reusing the completed one.
- Make `process_research_async` claim from `researching` as well as `pending`,
  and restore the previous terminal status if the claim fails.
- Add an explicit status-restore endpoint (e.g. `PATCH /research/{id}/status`)
  so operators and agents can recover stuck items.

### Tests to add

- `test_research_intent_on_completed_item_keeps_complete` — chat `research`
  intent against a `complete` item must not flip its status (or must create a
  new item).
- `test_research_intent_claim_failure_restores_status`.

---

## [P1] `tags` and `user_notes` are not persisted on create/update

### Symptom

`tags` submitted to `POST /research` are silently dropped
(`GET /research/{id}` returns `"tags": null`), and `PATCH /research/{id}`
only updates `query` — both `user_notes` and `tags` are ignored even though
the schema and the docstring say they are supported.

### Steps to reproduce

1. `POST /research` with `{"query": "...", "user_notes": "x", "tags": ["a"]}`.
2. `GET /research/{id}` → `user_notes` present, `tags` is `null`.
3. `PATCH /research/{id}` with `{"user_notes": "y", "tags": ["b"]}`.
4. `GET /research/{id}` → neither field changed.

### Root cause

`app/routers/research.py`:

- `create_research` builds
  `models.Research(query=..., user_notes=..., status="pending")` and never
  applies `payload.tags`.
- `update_research` only handles `payload.query`, ignoring `payload.user_notes`
  and `payload.tags` (contradicting its docstring: "Update research query,
  user notes, or tags.").
- `create_batch_research` likewise drops `tags` (and `user_notes`).

### Impact

- Tag-based filtering/organization does not work through the API.
- API consumers get documented fields silently ignored — confusing for humans
  and automated agents alike.

### Suggested fix

- In `create_research` and `create_batch_research`: persist `payload.tags`
  (and `payload.user_notes` in batch).
- In `update_research`: apply `payload.user_notes` and `payload.tags` when they
  are not `None`.

### Tests to add

- `test_create_research_persists_tags`
- `test_update_research_persists_user_notes_and_tags`
- `test_batch_create_persists_tags`
