# llm-researcher
An autonomous researcher agent powered by FastAPI, LangChain, and PostgreSQL.

## Stack

- **FastAPI** – REST API framework
- **LangChain** – LLM orchestration with multiple provider support
- **PostgreSQL** – Persistent storage for research results
- **Docker / Docker Compose** – Containerized deployment

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

### Makefile Commands

| Command         | Description                             |
|-----------------|-----------------------------------------|
| `make up`       | Start all services in the background    |
| `make down`     | Stop all services                       |
| `make build`    | Build Docker images                     |
| `make restart`  | Rebuild and restart all services        |
| `make dev`      | Start services with live logs           |
| `make logs`     | Follow logs (use `svc=app` to filter)   |
| `make shell`    | Open a shell in the app container       |
| `make db-shell` | Open a psql shell in the db container   |
| `make test`     | Run the test suite inside the container |
| `make lint`     | Run the linter inside the container     |

### API Endpoints

Once running, the API is available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

| Method | Path             | Description                 |
|--------|------------------|-----------------------------|
| GET    | `/`              | Health check                |
| POST   | `/research`      | Submit a new research query |
| GET    | `/research`      | List all research results   |
| GET    | `/research/{id}` | Get a specific result       |

### Example

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest advances in quantum computing?"}'
```
