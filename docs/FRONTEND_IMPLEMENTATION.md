# Frontend UI Implementation Summary

**Last updated**: 2026-08-10

## Overview

The frontend is a React 18 + TypeScript + Vite + Tailwind CSS application,
served by Nginx and proxying API/WebSocket traffic to the FastAPI backend.

- **Web UI**: http://localhost:3000 (via `make up`)
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## What's Implemented

### Research management
- Create research queries (with optional notes)
- List research with pagination, status filtering, and search
- Edit query / notes / tags inline (`EditableResearchHeader.tsx`)
- Delete, cancel, and resume research

### Research detail — 10 tabs
Overview (metrics + timeline) · Plan · Sources · Findings · Entities ·
Result · Knowledge Base · Notes · Agent Steps · Chat

### Knowledge base CRUD
- Sources: add/edit/delete via modal forms, filter by type/tag/search,
  sort by relevance, per-source notes and tags
- Findings: add/edit/delete via modal forms, filter/search, link to sources
- Notes: create/edit/delete with agent attribution
  (planner / search / hypothesis / synthesis / user)

### Real-time & transparency
- WebSocket progress stream (`createWebSocket()` in `api/client.ts`)
- Research plan visualization (`ResearchPlanTab.tsx`) and AI state inspector
  (`StateInspector.tsx`)
- Agent execution timeline (`AgentSteps.tsx`, `TimelineView.tsx`)

### Exports
- `ExportMenu.tsx` triggers document exports (PDF/HTML/DOCX/Markdown) and
  data exports (BibTeX/CSV/JSON) using the backend export endpoints

### UX polish
- Toast notifications (`Toast.tsx`, `toastContext.ts`)
- Confirmation dialogs (`ConfirmDialog.tsx`)
- Loading/empty/error states and responsive layout

### Settings
- `SettingsPage.tsx` implements runtime settings editing (list/update/clear
  overrides against `/settings`). **Note**: not yet wired into navigation.

## Production Architecture

```
┌──────────────────────────────────────┐
│ Nginx (port 80 in container)         │
│ Exposed as port 3000 on host         │
│                                      │
│ Serves: React static files           │
│ Proxies: /api/* → app:8000/*         │
│ Proxies: /ws/*  → app:8000/ws/*      │
└──────────────────────────────────────┘
```

## Development

```bash
cd frontend
npm install
npm run dev   # hot reload on :3000, proxied to :8000
```

## Known Limitations

1. Research list polls every 10 seconds instead of using WebSocket push.
2. No pagination in the sources/findings UI (backend supports `skip`/`limit`).
3. No bulk operations (select multiple → batch delete/tag/export).
4. `SettingsPage.tsx` exists but isn't reachable from navigation.
5. No frontend unit tests or E2E tests yet (see ROADMAP Milestone 1).
6. No dark mode / i18n / PWA.

## Testing

The UI is validated by manual smoke checks (create → monitor → edit →
export). Automated frontend tests are planned — see
[ROADMAP.md](ROADMAP.md) Milestone 1.

## Docs

- [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) — architecture and component guide
- [frontend/README.md](../frontend/README.md) — setup and scripts
- [STATUS_REPORT.md](STATUS_REPORT.md) — overall project status
