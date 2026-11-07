# Phase 2 — Document ingestion and retrieval

## What this phase delivers
- Create and list projects.
- Upload PDF, DOCX, Markdown and TXT requirements documents (15 MB maximum).
- Extract text, split it into overlapping chunks, generate OpenAI `text-embedding-3-small` embeddings (1536 dimensions), and store vectors in PostgreSQL/pgvector.
- Retrieve the top matching chunks for a question using cosine similarity. Results include source filename and chunk index for traceability.

## Prerequisites
- Phase 1 Docker Compose stack running.
- An OpenAI API key with access to the embeddings endpoint. It is used for embeddings only in this phase; no chat completion is called.

## Apply the Phase 2 database migration
From the project root in WSL:

```bash
docker compose exec -T postgres psql -U reqflow -d reqflow -f /docker-entrypoint-initdb.d/003_phase2_rag.sql
```

This is required because PostgreSQL's init scripts only run when the data volume is first created. Do not run `docker compose down -v`—that deletes your database volume.

## Configure and rebuild
Add your key to `.env`:

```dotenv
OPENAI_API_KEY=your_actual_key_here
```

Then:

```bash
docker compose up -d --build backend
```

## API walkthrough
1. Open `http://localhost:8000/docs`.
2. `POST /api/v1/projects` with `{"name":"Student Attendance Management","description":"BRD ingestion and requirements discovery"}`.
3. Copy the returned project `id`.
4. `POST /api/v1/projects/{project_id}/documents` as multipart form-data; field name `file`; select `data/sample_brd/student-attendance-management.md`.
5. `GET /api/v1/projects/{project_id}/documents` and confirm `processing_status=completed` and `chunk_count > 0`.
6. `POST /api/v1/rag/search` with `{"project_id":"<UUID>","question":"What attendance alerts and reports are required?","top_k":5}`.
7. Confirm each result has a filename, chunk index, content and similarity score.

## Important limitations
- Scanned/image-only PDFs need OCR; this phase intentionally reports that no extractable text was found.
- Embedding calls are billable according to your OpenAI account. Uploading and re-indexing the same file creates a new document; delete/re-index management is a later enhancement.
- The retrieval endpoint returns grounded source chunks only. Phase 3 adds answer synthesis, citations and requirement extraction agents.
- This is a development scaffold: add authentication, malware scanning, stricter tenant authorization, background jobs and production secret management before deployment.
