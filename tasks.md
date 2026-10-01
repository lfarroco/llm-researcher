# Tasks — High-Priority Issues

**Last updated**: 2026-09-25

High-priority issues found during LLM-driven end-to-end testing of the
research pipeline. The test kit used to reproduce them is documented in
[`docs/LLM_TESTING.md`](docs/LLM_TESTING.md); the general roadmap lives in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

> **Session 2026-09-25:** the two tracked items below (P0 and P1) are fixed.
> The security items in the next section are deliberately deferred. A
> **release-blocking** defect was also found and fixed outside this tracker —
> an unpinned `bibtexparser` made a fresh `docker compose build` produce an app
> that could not start. That, plus the document-export, full-text-grounding,
> Wikipedia, `/plan` progress, hypothesis-attribution, domain-cap, timeout, CI
> and frontend fixes, are recorded in [`CHANGELOG.md`](CHANGELOG.md) and
> [`docs/HANDOFF.md`](docs/HANDOFF.md) §4.
>
> Still open: no dependency lockfile (the root cause of the above), web-source
> authors, content-similarity dedup, and the `/state` response shape. See
> HANDOFF §5.

Status legend:

- `[ ]` not started
- `[~]` in progress
- `[x]` fixed

---

## Deferred: security hardening (single-user / localhost deployments)

> **Decision (2026-09-25):** these are **known and accepted** for the current
> single-machine, single-operator deployment. They are recorded here so they are
> not forgotten before the app is exposed to a network or to other users. Do
> not "fix" them opportunistically without reading the note at the end of this
> section — the redaction change in particular affects the settings UI contract.

### [SEC-1] `GET /settings` returns every live API key in plaintext, unauthenticated

**Status**: `[ ]` deferred (accepted while localhost-only)

**Symptom.** `curl http://127.0.0.1:8000/settings` returns the real values of
`openai_api_key`, `groq_api_key`, `deepseek_api_key`, `tavily_api_key`,
`semantic_scholar_api_key`, `springer_api_key`, `elsevier_api_key` and
`ncbi_api_key` — in **both** the `value` and `default_value` fields of the
response. Confirmed against the running Docker stack.

**Root cause.** `app/routers/settings.py::list_settings` builds
`AppSettingResponse(value=getattr(settings, key), ...)` for every key in
`EDITABLE_SETTINGS`, and `get_setting_metadata()` fills `default_value` from
`get_env_setting_value(key)`. `SENSITIVE_SETTINGS` (`app/config.py`) and the
`sensitive` flag on `AppSettingResponse` exist, but **nothing ever consumes
them to redact** — the only reader is the frontend
(`frontend/src/components/SettingsPage.tsx`), which merely sets
`type="password"` on the input while the plaintext value is still prefilled in
the DOM.

**Why it is not just cosmetic.** Any process or user that can reach port 8000
(or port 3000 — nginx proxies `/api/` to the app) can read the keys. The app
binds `0.0.0.0` in Docker. There is no authentication on any route
(`app/main.py` registers no middleware or dependencies), and
`PUT`/`DELETE /settings/{key}` let any caller mutate runtime configuration.

**Fix when it matters.**
- Server-side redaction in `list_settings`/`upsert_setting`: for keys in
  `SENSITIVE_SETTINGS`, return a masked placeholder (e.g. last 4 characters or
  `null`) instead of the raw value, and omit the env value from
  `default_value`.
- Decide and document the UI contract for editing a redacted secret (typical
  pattern: show a masked placeholder, only send a new value when the operator
  actually types one — never echo the old one back).
- Add authentication + per-user isolation before any networked deployment
  (tracked as Milestone 5 in `docs/ROADMAP.md`).

**Note on key rotation.** Any key that was read while this endpoint was
reachable should be treated as disclosed and rotated.

### [SEC-2] No authentication or authorization on any endpoint

**Status**: `[ ]` deferred (accepted while localhost-only)

Every route is unauthenticated. Combined with the app binding `0.0.0.0`, any
host that can reach the API can create/delete research items, read the whole
knowledge base, change runtime settings, and trigger LLM spend. Treated as
Milestone 5 ("Authentication (JWT) + per-user data isolation") in
`docs/ROADMAP.md`; this entry exists so the gap is visible in the issue tracker
as well.

### [SEC-3] No CORS policy

**Status**: `[ ]` deferred (accepted while localhost-only)

`app/main.py` registers no `CORSMiddleware`. This currently *limits* browser
exposure (cross-origin JS cannot read responses), but it also means the
browser-facing contract is undefined and will need an explicit allow-list at
the same time as SEC-2 rather than a permissive default.

---

## [x] [P0] Completed research item can get stuck in `researching` status via chat

**Fixed** (2026-09-25). `handle_research_intent` no longer sets a status the
worker cannot claim:

- A `complete` item is **left alone** — the intent creates a *new* `Research`
  row (carrying over `user_notes`/`tags`), queues that, and returns its id as
  `state_changes["new_research_id"]`, so the finished report is never
  overwritten.
- Every other status is re-queued **in place** by resetting it to `pending`,
  which is what `process_research_async`'s atomic claim accepts. This also
  recovers items already stranded in `researching` by the old behaviour.
- Regression tests: `tests/test_chat_handlers.py` (including an end-to-end
  check that a re-queued item is actually claimed and reaches `complete`).

### Original report

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

## [x] [P1] `tags` and `user_notes` are not persisted on create/update

**Fixed** (2026-09-25).

- `create_research` now persists `payload.tags`.
- `update_research` applies `payload.user_notes` and `payload.tags` when they
  are not `None`.
- `create_batch_research` now persists both; `BatchResearchCreate` gained
  optional `user_notes`/`tags` fields (applied to every item in the batch),
  since the request schema previously could not express them at all.
- Regression tests in `tests/test_integration.py::TestResearchWorkflow`.

### Original report

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
