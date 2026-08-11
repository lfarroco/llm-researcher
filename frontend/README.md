# LLM Researcher UI

React + TypeScript frontend for the LLM Researcher system.

## Features

- Create, list, filter, edit, and delete research queries
- Real-time progress updates via WebSocket
- 10-tab research detail view (Overview, Plan, Sources, Findings, Entities,
  Result, Knowledge Base, Notes, Agent Steps, Chat)
- Full CRUD for sources, findings, and notes
- Exports (PDF/HTML/DOCX/Markdown, BibTeX/CSV/JSON)
- Plan visualization and AI state inspector
- Toast notifications and confirmation dialogs

## Development

```bash
# Install dependencies
npm install

# Start dev server (hot reload, proxies API to :8000)
npm run dev

# Type-check + production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint
```

The dev server runs at http://localhost:3000.

## Tech Stack

- **React 18** · **TypeScript** · **Vite** · **Tailwind CSS** · **WebSocket**

## Project Structure

```
src/
├── api/client.ts          # API client + WebSocket helper
├── components/            # UI components (ResearchList, ResearchDetail,
│                          #   KnowledgeBase, ResearchNotes, AgentSteps,
│                          #   ResearchPlanTab, StateInspector, modals, ...)
├── context/               # React context (toasts)
├── hooks/                 # Custom hooks (useToast)
├── types.ts               # TypeScript interfaces
├── App.tsx                # App shell + routing
└── main.tsx               # Entry point
```

## API Proxy

The Vite dev server proxies requests to avoid CORS:
- `/api/*` → `http://localhost:8000/*`
- `/ws/*` → `ws://localhost:8000/*`
