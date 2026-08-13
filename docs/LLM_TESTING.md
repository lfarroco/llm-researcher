# LLM Testing Guide

**Last updated**: 2026-08-13

A repeatable recipe for end-to-end testing of llm-researcher — written for
humans and for autonomous LLM agents. It explains how to run a research item
through the whole pipeline (create → poll → verify → export) in one command,
without needing Docker or PostgreSQL.

For a quick list of known issues found by this test kit, see
[`../tasks.md`](../tasks.md).

---

## 1. Prerequisites

- Python venv with dependencies installed: `.venv/` (or `pip install -r requirements.txt`).
- `.env` at the repo root with a working provider and search keys:
  - `LLM_PROVIDER` + provider key (e.g. `LLM_PROVIDER=groq`, `GROQ_API_KEY=...`)
  - `TAVILY_API_KEY` (web search; DuckDuckGo fallback works without it)

### Verify the LLM key before running (1 request)

```bash
source .env
curl -s https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":5}'
```

## 2. Quick start — one command

```bash
make e2e query="What is citizen reporting in smart cities?"
```

Equivalent (in-process mode, no server):

```bash
.venv/bin/python scripts/smoke_research.py "What is citizen reporting in smart cities?"
```

This boots the real app on an in-memory SQLite DB, creates the research item,
polls until a terminal status, verifies document/sources/findings, writes
artifacts to `smoke_artifacts/`, prints a JSON summary, and exits `0` on
success (non-zero on failure).

## 3. Run modes

| Mode | Command | Use when |
|---|---|---|
| **In-process** (default) | `python scripts/smoke_research.py "query"` | Fastest, most reliable for automated testing — no ports, no processes to manage. |
| **Live server** | `python scripts/smoke_research.py --live --base-url http://localhost:8000 "query"` | Testing a real deployment (`make local-dev`, `docker compose up -d`, CI). |

### Optional flags

```
--outdir PATH        artifact dir (default: smoke_artifacts)
--timeout SECONDS    max wait for completion (default: 600)
--poll-interval S    status poll interval (default: 5)
-v                   print each poll line
```

## 4. Running a dev server (for interactive/UI work)

```bash
make local-dev        # uvicorn on http://127.0.0.1:8000 with in-memory SQLite
make local-down       # stop it
```

- API docs: http://127.0.0.1:8000/docs
- Health check: `curl http://127.0.0.1:8000/` → `{"status":"ok",...}`
- Note: the default in-memory database is **ephemeral** — all data resets when
  the server stops.

## 5. API lifecycle cheat-sheet

All paths are relative to `http://localhost:8000`. Interactive docs at `/docs`.

### Create a research item

```bash
curl -X POST http://localhost:8000/research -H 'Content-Type: application/json' \
  -d '{"query": "What is citizen reporting in smart cities?", "user_notes": "note", "tags": ["smart-cities"]}'
# -> {"id": 1, "status": "pending", ...}
```

### Poll until done (Python one-liner)

```python
python - <<'EOF'
import json, time, urllib.request
rid = 1
while True:
    item = json.load(urllib.request.urlopen(f"http://localhost:8000/research/{rid}"))
    print(item["status"], len(item.get("result") or ""))
    if item["status"] in {"complete", "completed", "failed", "error", "cancelled"}:
        break
    time.sleep(5)
EOF
```

### Verify and fetch outputs

| Endpoint | Returns |
|---|---|
| `GET /research/{id}` | status, result, notes, timestamps |
| `GET /research/{id}/document` | `{id, query, document, status, sources, ...}` |
| `GET /research/{id}/sources` | list of collected citations |
| `GET /research/{id}/findings` | list of per-sub-query findings |
| `GET /research/{id}/plan` | sub-queries + progress |
| `GET /research/{id}/knowledge-base` | sources grouped by sub-query |
| `GET /research/{id}/entities` | extracted entities |
| `GET /research/{id}/state` | full LangGraph state |
| `GET /research/{id}/steps` | agent execution steps |
| `GET /research/{id}/export/markdown` | Markdown document |
| `GET /research/{id}/export/pdf` · `html` · `docx` | pandoc-based exports |
| `GET /research/{id}/export/sources/bibtex` | BibTeX |
| `POST /research/{id}/chat` | chat with intent router |

### Status lifecycle

```
pending -> planning -> researching -> complete        (normal path)
                              \-> failed | error      (failure)
                              \-> cancelled           (user cancel)
```

- `POST /research/{id}/resume` only works from `cancelled` / `error` / `failed`.
- There is **no** endpoint to reset status — see `tasks.md` P0.

## 6. Verification checklist (what a passing run must show)

- [ ] `POST /research` returns `201` with `status=pending`
- [ ] status reaches `complete` within the timeout
- [ ] `GET /research/{id}/result` is a non-empty document (~4–10 KB)
- [ ] `GET /research/{id}/sources` has > 0 items
- [ ] `GET /research/{id}/findings` has ≥ 1 item
- [ ] `GET /research/{id}/export/markdown` returns `200` and non-empty body

The smoke script checks all of these automatically.

## 7. Known quirks & workarounds

Tracked with full repro steps in [`../tasks.md`](../tasks.md):

- **P0 — Stuck `researching` status via chat**: a chat message classified as a
  *research* intent on an already-completed item flips it to `researching`
  forever (no re-run, no reset endpoint). **Workaround**: don't send
  research-intent chat messages to completed items; use a fresh item.
- **P1 — `tags`/`user_notes` not persisted**: `tags` are dropped on create, and
  `PATCH /research/{id}` only updates `query`. **Workaround**: don't rely on
  tags in E2E assertions; treat `PATCH` as query-only for now.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `Network error ... Is the server running?` | Start it (`make local-dev` or `docker compose up -d`) or drop `--live`. |
| Research fails with 0 sources | Check `TAVILY_API_KEY` in `.env`; the app falls back to DuckDuckGo, which is slower/less reliable. |
| PDF/HTML/DOCX export fails | These need `pandoc` installed (`check_pandoc_installed`); use the Markdown export instead. |
| `429 rate limited` on create | The API rate-limits research creation (default 10/min per client IP); wait and retry. |
| File-based SQLite `check_same_thread` errors | Use the default `:memory:` DB (see `scripts/dev_server.py` notes). |
| Stuck item | See `tasks.md` P0; restart the dev server to reset an in-memory DB. |
| Logs | Dev server writes to stdout; in-process smoke runs print progress with `-v`. |

