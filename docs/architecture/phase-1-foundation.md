# Phase 1 — Foundation

## Objective
Create a runnable monorepo with frontend, backend, database, cache and initial LangGraph skeleton.

## Architecture
- React + TypeScript
- FastAPI
- PostgreSQL 16 + pgvector
- Redis 7
- LangGraph typed state and intake graph
- Docker Compose

## Verification
1. `docker compose up --build -d`
2. `GET /health` returns `{"status":"ok","service":"reqflow-api"}`.
3. `GET /api/v1/system/info` reports Phase 1 components.
4. Frontend at port 3000 loads and displays backend connectivity.
5. PostgreSQL has the `vector` extension.

## Deferred
Authentication, project CRUD, document upload, RAG, specialized agents, MCP servers and external integrations.
