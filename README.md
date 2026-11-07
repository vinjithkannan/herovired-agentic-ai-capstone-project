# ReqFlow AI — Phase 1 Foundation

React + TypeScript, FastAPI, PostgreSQL + pgvector, Redis, Docker Compose and a LangGraph skeleton.

## Prerequisites
- Docker Desktop with WSL2 integration enabled (Windows) or Docker Engine + Compose
- Git
- Optional local development: Python 3.12 and Node.js 22

## Start
```bash
git clone <YOUR_REPOSITORY_URL>
cd reqflow-agentic-ai-capstone
cp .env.example .env
# Edit JWT_SECRET and credentials in .env
docker compose up --build -d
docker compose ps
```

Open:
- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- Swagger: http://localhost:8000/docs

Expected health response:
```json
{"status":"ok","service":"reqflow-api"}
```

## Useful commands
```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
# WARNING: deletes local database data
docker compose down -v
docker compose up --build -d
docker compose exec postgres psql -U reqflow -d reqflow
docker compose exec redis redis-cli ping
```

## Verify pgvector
```bash
docker compose exec postgres psql -U reqflow -d reqflow -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

## WSL local development (optional)
Backend:
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Frontend in another terminal:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```
For local frontend development, create `frontend/.env.local` with `VITE_API_BASE_URL=http://localhost:8000`.

## Phase 1 includes
- Monorepo and Docker Compose
- FastAPI health and system endpoints
- React starter dashboard with backend connectivity
- PostgreSQL + pgvector initialization and starter tables
- Redis
- Typed LangGraph state and intake-only graph
- Synthetic Student Attendance BRD

Authentication, CRUD, upload, RAG, six agents, MCP servers and Jira/GitHub integration are later phases.

This is a local development scaffold, not production-ready. Do not expose default credentials or database ports publicly. Add authentication, backups, secrets management and least-privilege access before deployment.


## Phase 2 — Document ingestion and RAG

Phase 2 adds project endpoints, PDF/DOCX/Markdown/TXT ingestion, text chunking, OpenAI embeddings (`text-embedding-3-small`), pgvector storage and cosine-similarity retrieval. Follow [`docs/phase-2/README.md`](docs/phase-2/README.md) to apply the migration and test the endpoints.


## Phase 3 — Agentic Requirements Analysis

Phase 3 adds a LangGraph workflow powered by local Ollama chat inference. It retrieves indexed BRD passages, extracts and classifies requirements, identifies quality issues and open questions, and validates source evidence. See [`docs/phase-3/README.md`](docs/phase-3/README.md) for setup, migration and testing instructions.

The Phase 2 embedding index is intentionally preserved. It uses 1536-dimensional OpenAI embeddings; Phase 3 uses the same embedding model for retrieval and Ollama for LLM reasoning. Configure `OPENAI_API_KEY` for embeddings and pull the Ollama chat model separately.
