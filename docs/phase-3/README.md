# Phase 3 — Agentic Requirements Analysis

## What this phase adds

A five-node LangGraph pipeline runs against the BRD passages already indexed in Phase 2:

1. `retrieve_context` — retrieves the most relevant indexed chunks for the project.
2. `extract_requirements` — extracts evidence-backed functional requirements, non-functional requirements, business rules and constraints.
3. `classify_requirements` — assigns categories, priority only where supported, ambiguity and testability.
4. `analyze_quality` — identifies ambiguity, missing implementation detail, duplicates, conflicts and open questions.
5. `validate_evidence` — checks that each extracted requirement is supported by source passages.

Ollama supplies local chat inference. The current Phase 2 embedding index remains unchanged: its `vector(1536)` values were generated with `text-embedding-3-small`, so query embeddings continue using the same provider/model. Do not switch to a 768-dimensional Ollama embedding model without rebuilding the entire index and changing the vector column dimension.

## 1. Configure Ollama

The Compose file adds an `ollama` service and persistent `ollama_data` volume. The default chat model is `qwen2.5:3b`.

From the project root:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama list
```

The first model download can take several minutes. The model remains in the `ollama_data` volume.

## 2. Apply the Phase 3 database migration

The existing PostgreSQL volume means this new SQL file is not auto-executed. Run once:

```bash
docker compose exec -T postgres psql -U reqflow -d reqflow -f /docker-entrypoint-initdb.d/004_phase3_analysis.sql
```

Verify:

```bash
docker compose exec postgres psql -U reqflow -d reqflow -c "\\dt analysis_runs"
```

Do not run `docker compose down -v`; it deletes your database and Ollama model volumes.

## 3. Rebuild and start

```bash
docker compose up -d --build backend frontend ollama
docker compose ps
```

If the backend was started before the Ollama model was pulled, it does not need a rebuild; it will call the model when analysis is requested.

## 4. Run an analysis

Open `http://localhost:3000`, select the project that contains the indexed BRD and click **Run requirements analysis**.

Or use Swagger `POST /api/v1/projects/{project_id}/analyze`:

```json
{
  "question": "Extract all requirements and identify unresolved questions from the BRD.",
  "top_k": 12
}
```

The response contains `requirements`, `quality_findings`, `open_questions`, `validation`, and source passages. Each requirement should include a `source_refs` quote and chunk index.

List persisted runs with `GET /api/v1/projects/{project_id}/analyses`.

## 5. Troubleshooting

- `Cannot reach Ollama`: run `docker compose ps ollama` and `docker compose logs --tail=100 ollama`. Inside the backend container the URL must be `http://ollama:11434`, not `localhost:11434`.
- `model not found`: run `docker compose exec ollama ollama pull qwen2.5:3b`.
- Slow first response: Ollama loads the model on first use. The API timeout defaults to 300 seconds; tune `OLLAMA_TIMEOUT_SECONDS` in `.env` if needed.
- Unsupported or fabricated requirement: treat output as a draft. Check the evidence quote and validation status before approval. The model is instructed not to infer missing features or assign unsupported priority.
- Retrieval failure: Phase 3 intentionally uses the same embedding provider as Phase 2 to preserve vector compatibility. Ensure the Phase 2 `OPENAI_API_KEY` is still configured.

## Scope and safety

This phase produces a reviewable analysis draft; it does not create Jira/GitHub tickets or approve requirements. Human review and approval gates, user-story generation, MCP integrations and external issue creation belong to later phases.
