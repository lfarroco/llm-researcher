# LLM Researcher — Frontend Guide

A modern, responsive React + TypeScript UI for the LLM Researcher system.

## Features

- **Research management**: create, list + filter, edit, delete, cancel/resume
- **Real-time progress**: WebSocket-driven live updates while researching
- **10-tab detail view**: Overview, Plan, Sources, Findings, Entities, Result,
  Knowledge Base, Notes, Agent Steps, Chat
- **Full CRUD** for sources, findings, and notes
- **Filtering & search** on the research list, sources, and findings
- **Exports** from the UI: PDF/HTML/DOCX/Markdown documents and
  BibTeX/CSV/JSON data
- **Transparency**: research plan visualization and AI state inspector
- **UX polish**: toast notifications, confirmation dialogs, loading/empty
  states, responsive layout

## Quick Start

### Using Docker (recommended)

```bash
# From project root
make up

# Access UI at http://localhost:3000
```

### Local development (hot reload)

```bash
cd frontend
npm install
npm run dev   # requires the backend running on port 8000
```

The dev server runs at http://localhost:3000 and proxies API/WebSocket
requests to the backend (no CORS issues).

## Architecture

```
frontend/
├── src/
│   ├── api/client.ts        # API client + WebSocket helper
│   ├── components/          # UI components (see below)
│   │   └── __tests__/       # Vitest unit tests
│   ├── context/             # React context (toasts)
│   ├── hooks/               # Custom hooks (useToast)
│   ├── types.ts             # TypeScript interfaces mirroring the API
│   ├── App.tsx              # App shell + routing
│   └── main.tsx             # Entry point
├── Dockerfile               # Multi-stage production build
├── nginx.conf               # Nginx proxy config
└── vite.config.ts           # Vite + dev proxy
```

## Key Components

### App-level
- `App.tsx` — routing (`/` research list, `/research/:researchId` detail,
  `/settings`)
- `api/client.ts` — typed wrappers around every backend endpoint
- `types.ts` — `Research`, `Source`, `Finding`, `ResearchNote`, etc.

### Research list
- `App.tsx` — research list table with status badges and filtering (rendered
  inline on the `/` route; polls every 10s while on the list page)
- `ResearchForm.tsx` — create a new research query (with optional notes)

### Research detail (10 tabs)
| Tab | Component(s) |
|---|---|
| Overview | `MetricsCards.tsx`, `TimelineView.tsx` |
| Plan | `ResearchPlanTab.tsx` |
| Sources | `SourcesFilterBar.tsx`, `SourceFormModal.tsx` |
| Findings | `FindingsFilterBar.tsx`, `FindingFormModal.tsx` |
| Entities | `ResearchEntitiesTab.tsx` |
| Result | inline markdown render |
| Knowledge Base | `KnowledgeBase.tsx` |
| Notes | `ResearchNotes.tsx` |
| Agent Steps | `AgentSteps.tsx`, `StateInspector.tsx` |
| Chat | `ChatInterface.tsx` |

### Shared
- `EditableResearchHeader.tsx` — inline editing of query/notes/tags
- `ExportMenu.tsx` — document + data export actions
- `ConfirmDialog.tsx` — reusable confirmation dialog
- `Toast.tsx` + `toastContext.ts` + `useToast.ts` — notifications
- `SearchInput.tsx` — debounced search input
- `SettingsPage.tsx` — runtime settings editor (reachable via the Settings
  navigation tab at `/settings`)

## Development

### Scripts

```bash
npm run dev       # dev server with hot reload
npm run build     # type-check (tsc) + production build
npm run preview   # preview the production build
npm run lint      # ESLint
npm test          # unit tests (Vitest + React Testing Library)
```

### Adding a new feature

1. Add types to `src/types.ts`
2. Add API methods to `src/api/client.ts`
3. Build components in `src/components/`
4. Wire into `App.tsx` / the relevant tab

## Production Build

The Docker image is multi-stage: a Node build stage compiles the app with
Vite, then an Nginx stage serves the static assets. Nginx proxies `/api/`
to the backend and upgrades `/ws/` to WebSocket.

## Styling

Tailwind CSS utility classes (see `tailwind.config.js`). Palette:
primary blue (research/links), green (completed), orange (pending),
red (failed/error).

## Troubleshooting

**"Connection failed" in the browser** — ensure the backend is running on
port 8000; check the browser console for proxy/CORS errors.

**WebSocket not connecting** — verify the backend WebSocket endpoint directly:
`ws://localhost:8000/ws/research/<id>`.

**Build fails** — `rm -rf node_modules && npm install`; requires Node 18+.

## License

Same as parent project — MIT (see `LICENSE` at the repo root).
