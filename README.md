# llm-researcher
An autonomous researcher agent powered by FastAPI, LangChain, and PostgreSQL.

## Stack

- **FastAPI** – REST API framework
- **LangChain** – LLM orchestration (OpenAI GPT-4o by default)
- **PostgreSQL** – Persistent storage for research results
- **Docker / Docker Compose** – Containerized deployment

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Setup

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### Makefile Commands

| Command        | Description                              |
|----------------|------------------------------------------|
| `make up`      | Start all services in the background     |
| `make down`    | Stop all services                        |
| `make build`   | Build Docker images                      |
| `make restart` | Rebuild and restart all services         |
| `make dev`     | Start services with live logs            |
| `make logs`    | Follow logs (use `svc=app` to filter)    |
| `make shell`   | Open a shell in the app container        |
| `make db-shell`| Open a psql shell in the db container   |
| `make test`    | Run the test suite inside the container  |
| `make lint`    | Run the linter inside the container      |

### API Endpoints

Once running, the API is available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

| Method | Path                    | Description                  |
|--------|-------------------------|------------------------------|
| GET    | `/`                     | Health check                 |
| POST   | `/research`             | Submit a new research query  |
| GET    | `/research`             | List all research results    |
| GET    | `/research/{id}`        | Get a specific result        |

### Example

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest advances in quantum computing?"}'
```
