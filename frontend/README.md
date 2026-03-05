# LLM Researcher UI

React + TypeScript frontend for the LLM Researcher system.

## Features

- 📝 Create and manage research queries
- 📊 Real-time progress updates via WebSocket
- 📚 View sources and findings
- 💬 Chat with research results
- 🎨 Clean, modern UI with Tailwind CSS

## Development

```bash
# Install dependencies
npm install

# Start development server (with API proxy)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The dev server runs on `http://localhost:3000` with automatic proxy to the backend API at `http://localhost:8000`.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first styling
- **WebSocket** - Real-time updates

## Project Structure

```
src/
├── api/
│   └── client.ts         # API client and WebSocket
├── components/
│   ├── ChatInterface.tsx    # Chat with research
│   ├── ProgressMonitor.tsx  # WebSocket progress viewer
│   ├── ResearchDetail.tsx   # Main detail view with tabs
│   ├── ResearchForm.tsx     # Create new research
│   └── ResearchList.tsx     # List of research queries
├── types.ts              # TypeScript interfaces
├── App.tsx               # Main app component
├── main.tsx              # Entry point
└── index.css             # Global styles
```

## API Proxy Configuration

The Vite dev server proxies API requests:
- `/api/*` → `http://localhost:8000/*`
- `/ws/*` → `ws://localhost:8000/*`

This avoids CORS issues during development.
