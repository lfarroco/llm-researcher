# LLM Researcher - Frontend UI

A modern, responsive React + TypeScript UI for the LLM Researcher system.

## ✨ Features

- **📝 Research Management**: Create and track research queries
- **🔍 Real-time Progress**: WebSocket-powered live updates
- **📚 Sources & Findings**: Browse collected sources and extracted findings
- **💬 Interactive Chat**: Ask questions about research results
- **🎨 Modern UI**: Clean design with Tailwind CSS
- **📱 Responsive**: Works on desktop and mobile

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# From project root
make up

# Access UI at http://localhost:3000
```

### Local Development

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (requires backend running)
npm run dev

# Access at http://localhost:3000
```

## 📐 Architecture

```
frontend/
├── src/
│   ├── api/            # API client and WebSocket
│   ├── components/     # React components
│   ├── types.ts        # TypeScript types
│   ├── App.tsx         # Main app
│   └── main.tsx        # Entry point
├── Dockerfile          # Production build
├── nginx.conf          # Nginx proxy config
└── vite.config.ts      # Vite configuration
```

## 🔧 Technology

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Lightning-fast build tool
- **Tailwind CSS** - Utility-first styling
- **WebSocket** - Real-time updates

## 🎯 Key Components

### ResearchForm
Create new research queries with optional notes.

### ResearchList
Browse all research queries with status indicators.

### ResearchDetail
Main detail view with tabs:
- **Overview**: Summary and key metrics
- **Sources**: All collected sources
- **Findings**: Extracted findings
- **Progress**: Real-time WebSocket updates
- **Chat**: Interactive Q&A

### ProgressMonitor
Live WebSocket event stream showing research progress.

### ChatInterface
Chat with the AI about research findings.

## 🛠️ Development

### Available Scripts

```bash
npm run dev      # Start dev server
npm run build    # Build for production
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

### Environment

The dev server proxies API requests to avoid CORS:
- `/api/*` → `http://localhost:8000/*`
- `/ws/*` → `ws://localhost:8000/*`

### Adding New Features

1. Add types to `src/types.ts`
2. Create API methods in `src/api/client.ts`
3. Build components in `src/components/`
4. Update `App.tsx` if needed

## 📦 Production Build

The Docker image uses multi-stage builds:
1. **Build stage**: Compiles React app with Vite
2. **Production stage**: Serves with Nginx

Nginx proxies API and WebSocket requests to the backend.

## 🎨 Styling

Uses Tailwind CSS utility classes. Customize in `tailwind.config.js`.

Color scheme:
- Primary: Blue (research, links)
- Success: Green (completed)
- Warning: Orange (pending)
- Error: Red (failed)

## 🔗 API Integration

All API calls go through `src/api/client.ts`:

```typescript
import { api } from './api/client';

// Create research
const research = await api.createResearch('My query');

// Get sources
const sources = await api.getSources(research.id);

// WebSocket
const ws = createWebSocket(research.id);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## 🐛 Troubleshooting

**"Connection failed" in browser**
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Verify proxy configuration in `vite.config.ts`

**WebSocket not connecting**
- Check WebSocket URL in network tab
- Ensure backend WebSocket endpoint is working
- Try accessing `ws://localhost:8000/ws/research/<id>` directly

**Build fails**
- Clear node_modules: `rm -rf node_modules && npm install`
- Check Node version: requires Node 18+
- Verify all dependencies installed

## 📄 License

Same as parent project.

---

Built with ❤️ using React, TypeScript, and Vite
