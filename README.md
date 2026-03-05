# llm-researcher
An autonomous researcher agent powered by FastAPI, LangChain, and PostgreSQL.

## 📚 Documentation

- **[STATUS_REPORT.md](docs/STATUS_REPORT.md)** - Implementation status and feature summary
- **[PLAN.md](docs/PLAN.md)** - Complete architecture plan and roadmap
- **[PHASE16_SUMMARY.md](docs/PHASE16_SUMMARY.md)** - Real-time WebSocket features guide
- **[FRONTEND_GUIDE.md](docs/FRONTEND_GUIDE.md)** - Frontend architecture and development
- **[FRONTEND_IMPLEMENTATION.md](docs/FRONTEND_IMPLEMENTATION.md)** - UI implementation summary

## Stack

- **Backend**: FastAPI + LangChain + LangGraph
- **Frontend**: React + TypeScript + Tailwind CSS
- **Database**: PostgreSQL
- **Deployment**: Docker + Docker Compose

## LLM Providers

This project supports multiple LLM providers:

- **OpenAI** – GPT-4o, GPT-4, GPT-3.5-turbo, etc.
- **Ollama** – Local models like qwen3:4b, llama2, mistral, etc.

Configure your preferred provider in the `.env` file.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)
- **For OpenAI**: An [OpenAI API key](https://platform.openai.com/api-keys)
- **For Ollama**: [Ollama installed](https://ollama.ai/) with your desired model pulled

### Setup

```bash
cp .env.example .env
# Edit .env and configure your LLM provider
```

#### Using Ollama (Local Models)

```bash
# In your .env file:
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://localhost:11434
```

Make sure Ollama is running and the model is pulled:
```bash
ollama pull qwen3:4b
ollama serve
```

#### Using OpenAI

```bash
# In your .env file:
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=your_api_key_here
```

### Start the Application

```bash
# Start all services (backend, frontend, database)
make up

# View logs
make logs

# Or filter by service
make logs svc=frontend
```

Once started, access:
- **Web UI**: http://localhost:3000 (React frontend)
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Frontend Development

For frontend development with hot-reload:

```bash
# Install dependencies (first time only)
cd frontend && npm install

# Start dev server
npm run dev
```

The dev server runs on port 3000 with automatic proxy to the backend API.

See [frontend/README.md](frontend/README.md) for more details.

### Makefile Commands

#### Core Commands
| Command        | Description                           |
|----------------|---------------------------------------|
| `make up`      | Start all services in the background  |
| `make down`    | Stop all services                     |
| `make build`   | Build Docker images                   |
| `make restart` | Rebuild and restart all services      |
| `make logs`    | Follow logs (use `svc=app` to filter) |
| `make help`    | Show all available commands           |

#### Backend Commands  
| Command      | Description                               |
|--------------|-------------------------------------------|
| `make shell` | Open a shell in the app container         |
| `make test`  | Run the test suite inside the container   |
| `make e2e`   | Run end-to-end integration test           |
| `make ws`    | Run WebSocket and real-time features test |
| `make lint`  | Run the linter inside the container       |

#### Frontend Commands
| Command                 | Description                            |
|-------------------------|----------------------------------------|
| `make frontend-dev`     | Start frontend dev server (hot reload) |
| `make frontend-build`   | Build frontend for production          |
| `make frontend-install` | Install frontend dependencies          |

#### Database Commands
| Command         | Description                           |
|-----------------|---------------------------------------|
| `make db-shell` | Open a psql shell in the db container |
| `make migrate`  | Run pending migrations                |

### API Endpoints

Once running, the API is available at `http://localhost:8000`.

**Interactive API Documentation**: 
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### Core Research Endpoints
| Method | Path                    | Description                      |
|--------|-------------------------|----------------------------------|
| GET    | `/`                     | Health check                     |
| POST   | `/research`             | Create a new research query      |
| POST   | `/research/batch`       | Create multiple research queries |
| GET    | `/research`             | List all research results        |
| GET    | `/research/{id}`        | Get a specific research result   |
| POST   | `/research/{id}/cancel` | Cancel a running research task   |
| POST   | `/research/{id}/resume` | Resume a paused research task    |
| DELETE | `/research/{id}`        | Delete a research result         |

#### Sources & Findings
| Method | Path                            | Description                  |
|--------|---------------------------------|------------------------------|
| GET    | `/research/{id}/sources`        | Get all sources for research |
| POST   | `/research/{id}/sources`        | Add a source manually        |
| GET    | `/research/{id}/findings`       | Get all findings             |
| POST   | `/research/{id}/findings`       | Create a finding manually    |
| PUT    | `/research/{id}/findings/{fid}` | Update a finding             |
| DELETE | `/research/{id}/findings/{fid}` | Delete a finding             |

#### AI State & Chat
| Method | Path                   | Description                    |
|--------|------------------------|--------------------------------|
| GET    | `/research/{id}/state` | View LangGraph agent state     |
| GET    | `/research/{id}/plan`  | View research plan/sub-queries |
| POST   | `/research/{id}/chat`  | Chat with the research results |

#### Real-time Updates
| Protocol  | Path                | Description                       |
|-----------|---------------------|-----------------------------------|
| WebSocket | `/ws/research/{id}` | Stream real-time progress updates |

See [PHASE16_SUMMARY.md](docs/PHASE16_SUMMARY.md) for WebSocket event details.

### Example

```bash
# Create a research query
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest advances in quantum computing?"}'

# Monitor progress via WebSocket (JavaScript)
const ws = new WebSocket('ws://localhost:8000/ws/research/1');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```
