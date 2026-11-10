# ReqFlow AI — Final Agentic AI Capstone Project Report

**Selected use case:** Requirements to User Story Automation (finalized use case #83)  
**Project:** ReqFlow AI — Requirements to Sprint-Ready Delivery  
**Case study:** Synthetic Student Attendance Management System BRD  
**Document date:** 10 November 2026  
**Status:** Functional capstone proof of concept; partial backlog approval disclosed

> **Evidence policy:** The screenshots in `data/screenshots/` record observed project execution and validation. They demonstrate the specific runs shown; they are not a production certification. The Phase 7 design and plan are proposals requiring technical/team review even though their workflow records have Product Owner approval.

## Executive summary

ReqFlow AI converts a business requirements document into source-grounded functional/non-functional requirements, an epic and user-story backlog with Given–When–Then acceptance criteria, quality findings, controlled Product Owner reviews, proposed solution architecture, and developer tasks with dependencies and provisional estimates. The app is a React/Vite frontend backed by FastAPI, PostgreSQL/pgvector, Redis, Ollama and LangGraph; GitHub/Jira integration is exposed through a controlled publishing service and a real MCP stdio server/client demonstration.

**Observed final results:** 10 generated stories; 4 quality-cleared **and** Product Owner–approved stories (US-001–US-004); 12 proposed implementation-plan tasks (four design, four implementation, four testing); eight of eight authenticated live smoke checks passed; **58** Docker-run Python tests passed; artifact-content audit `passed: true`; and the MCP client discovered three tools and invoked `preview_quality_cleared_story` with `writes_performed: false`. Five stories still required review and one remained blocked. Full backlog finalization is not claimed.

## 1. Selected use case and scope

The `usecases_final_list` workbook selected **Requirements to User Story Automation**. Its original description called for reading business requirements, creating user stories and acceptance criteria, preparing solution-design documents, creating implementation tasks and estimating effort. The listed conceptual roles were **Research Agent, Document Creation Agent and Planning Agent**. This project implements those functions through source-backed LangGraph requirements/story workflows and deterministic Phase 7 design and planning agents. It does **not** claim autonomous, LLM-invented solution architecture.

The accompanying APIs/MCPs/Data Sources workbook was used as an integration discovery reference, **not** a mandate to connect every cataloged service. The implemented and demonstrated external targets are GitHub Issues and Jira Cloud, with PostgreSQL/pgvector document retrieval and Ollama local inference.

### Inclusion and boundaries

- Included: synthetic BRD ingestion, RAG/evidence, analysis, epics/stories/AC, quality gate, repair and versioning, PO clarification, evaluation, RBAC, design/plan workflow, read-only MCP demonstration, controlled Jira/GitHub publishing.
- Excluded: building the actual university attendance product, production security certification, full automatic Jira sprint planning, bidirectional issue synchronization, and a validated real-world performance SLA for NFR-004.
- All attendance requirements are demonstration data, not a live university deployment.

## 2. Source BRD and requirement coverage

**Input document:** `data/sample_brd/student-attendance-management.md` (synthetic, version 1.0, Document ID BRD-ATT-001). It defines the university attendance business objective, five functional requirements (FR-001–FR-005), four NFRs (NFR-001–NFR-004), access and audit rules, six open questions, and exclusions such as biometrics and GPS.

| Requirement | Source meaning | Demonstration handling |
|---|---|---|
| BRD-ATT-001 | Centralized attendance management objective | Business-level traceability; should not be forced into a duplicate story |
| FR-001 | Faculty record attendance for assigned courses | Eligible story US-001 |
| FR-002 | Students view their attendance and percentage | Included in approved eligible backlog |
| FR-003 | Department attendance reports | Included in approved eligible backlog |
| FR-004 | Course, semester and academic-year context | Included in approved eligible backlog |
| FR-005 | Authorized correction and audit trail | Clarification/review remains |
| NFR-001 | Role- and scope-based access | Clarification/review remains |
| NFR-002 | Auditable creation/correction | Clarification/review remains |
| NFR-003 | Service availability | Quantified target not established in source |
| NFR-004 | Acceptable report/list response time | Numeric percentile/load target not established; one blocking quality finding |

**Coverage evidence:** A ten-ID human-reviewed golden set including BRD-ATT-001 matched 10/10 IDs (ID precision/recall/F1 = 1.00). An alternate nine-ID FR/NFR-only golden set produced 0.90 precision, 1.00 recall and 0.9474 F1 because the valid business ID was outside its scope. The implementation-backlog FR/NFR coverage was 9/9. These numbers measure **identifier matching**, not semantic correctness of generated stories, architecture or acceptance criteria.

## 3. System architecture

```text
User / Product Owner (browser)
       |
       v
React + TypeScript / Vite UI  -- Bearer session / RBAC -->  FastAPI API
                                                         |       |       |
                                                         |       |       +--> Publishing service --> GitHub / Jira
                                                         |       +--> LangGraph analysis / story / delivery graphs
                                                         +--> PostgreSQL + pgvector (projects, chunks,
                                                               analyses, backlogs, decisions, audits)
                                                           --> Redis (supporting infrastructure)
LangGraph requirements/story workflows --> Ollama qwen2.5:3b (generation)
Document embeddings --> Ollama nomic-embed-text (768 dimensions)
Separate MCP stdio client <--> MCP publishing server --> validated read-only preview
```

Five Docker Compose services are used: `postgres`, `redis`, `ollama`, `backend`, `frontend`. Existing PostgreSQL and model volumes are persistent. Sensitive `.env` and runtime uploads are excluded from the submission.

The **Phase 7 solution design** for the attendance *target application* is a **proposed** five-layer architecture: Client/UI → Authenticated API → Application services → Persistent database → Audit/observability. It is an output artifact of ReqFlow, not evidence that the proposed attendance application has been coded or deployed.

## 4. Agent architecture and workflow

### Research Agent — document grounding

Uploads are parsed and chunked. `nomic-embed-text` generates 768-dimensional embeddings stored in pgvector. Semantic search retrieves BRD passages with source document/chunk attribution. The Phase 3 LangGraph workflow uses Ollama `qwen2.5:3b` to extract/classify requirements, identify gaps and open questions, and attach evidence. Unsupported or incomplete output remains subject to validation.

### Story/Document Creation Agent — backlog generation

A LangGraph workflow creates epics, stories and Given–When–Then acceptance criteria. Quality checks detect unsupported evidence, weak testability, mismatched requirements, duplicate/cyclic stories, and unresolved assumptions. Targeted repair saves new versions while retaining the source backlog. Quality clearance is **separate** from Product Owner approval.

### Solution Design Agent — design proposal

The Phase 7 downstream LangGraph graph reuses saved verified analysis and eligible stories. Deterministic synthesis creates component responsibilities, architecture flow, proposed API endpoints, candidate data entities/fields, traceable acceptance criteria, assumptions, and open design decisions. Suggested attendance endpoints and entities are **not implemented endpoints or approved BRD facts**. Design approval is persisted independently.

### Implementation Planning Agent — task proposal

Only stories that are **both** quality-cleared and individually Product Owner–approved proceed. The planner creates three task types for each eligible story: design, implementation and testing. Dependencies link execution order. It records priority, story mapping, requirements/criteria traceability, provisional story points, and explicit `team_estimation_required` where unavailable. Plan approval is a second human gate.

### Unified orchestration

```text
BRD -> RAG / Research -> Requirements -> Story generation & quality review
        -> PO approval on eligible stories -> Design synthesis -> PO design gate
        -> Task planning -> PO plan gate -> Delivery artifact ready
```

The downstream orchestrator in `agents/orchestrator/graph.py` reads persisted verified outputs. It does **not** rerun Ollama, autonomously approve artifacts, or publish to external providers. A not-approved design halts progression before planning.

## 5. Seven-phase implementation record

| Phase | Scope | Evidence or source |
|---|---|---|
| 1 | Docker Compose, PostgreSQL/pgvector, Redis, backend/frontend foundation | `01`–`04` screenshots; init 001–002 |
| 2 | BRD ingestion, chunking, embeddings and semantic RAG | `05`–`06`; init 003 |
| 3 | Evidence-backed LangGraph requirements analysis and quality findings | `07`; init 004 |
| 4 | Epics, user stories, AC, quality gates, repair/versioning | `08`–`09`; init 005 |
| 5 | Publishing service, MCP server, Jira/GitHub controlled delivery | `10`–`11`, `19`–`20`; init 006 |
| 6 / 6.1 | Sessions, RBAC, audits, evaluation, PO clarifications and approval workflows | `09`, test evidence; init 007–008 |
| 7 | Readiness/reporting, solution design, planning, human-gated orchestration, MCP demo, audits | `12`–`23`; init 009 |

All phases have implemented source and selected observed evidence. A seven-phase development history is not equivalent to full clearance of all ten backlog stories.

## 6. API and MCP integration contracts

### Internal API surface

FastAPI exposes health/system endpoints, project and document operations, requirements analysis, backlog listing and story reviews, clarification proposals/decisions, evaluation, publishing preview/live routes, audit/operations and Phase 7 delivery views/approval actions. Swagger is available under `/docs`. The Phase 7 design Markdown export follows:

`GET /api/v1/projects/{project_id}/backlogs/{backlog_id}/delivery/design.md`

The full generated OpenAPI specification in the running service is the authority for method and schema details. Example **proposed attendance-product** endpoints in the design artifact (e.g. `GET /api/v1/attendance`) are not ReqFlow backend API claims.

### MCP server/client demonstration

The local stdio MCP server exposes `preview_quality_cleared_story`, `publish_approved_story`, and `list_story_publications`. The real Python MCP client successfully discovered all three and called the **preview** tool for `US-001`, GitHub target `vinjithkannan/herovired-agentic-ai-capstone-project`:

- `mode: dry_run`; `eligible: true`; `approval_status: approved`;
- `quality_status: quality_cleared`; `is_error: false`;
- `writes_performed: false`.

The MCP **publish** tool was discovered but **not invoked** in this validation. Separate earlier screenshots show a GitHub issue and a Jira issue created through the application's provider integration; do not conflate those earlier live publications with the MCP read-only demo.

### Publishing safety

Live issue publishing remains guarded by clearance, approval, explicit live enablement, authorization, audit and duplicate-prevention reservations. Ambiguous remote outcomes require reconciliation instead of blind retries. The MCP server is a separate integration surface; the React frontend talks to FastAPI rather than directly to MCP.

## 7. Database and security

PostgreSQL schema migrations `001`–`009` implement extensions, project/document storage, RAG chunks, analysis runs, backlog runs, publication records, security/evaluation, clarifications and Phase 7 `delivery_artifacts`. Existing installations require manual application of missing migrations because Docker init scripts only run on an empty database volume. PostgreSQL/pgvector and Redis health were verified in earlier phases.

Authentication uses server-side revocable bearer sessions, hashed token records, global application roles (`admin`, `product_owner`, `engineer`, `viewer`) and audit logging. The frontend's development session restoration uses browser-tab session storage; this is **not** a production-grade secure HttpOnly cookie deployment. Product Owner approval is not substituted for independent quality clearance.

## 8. Measured validation and results

| Validation | Observed result | Scope / caveat |
|---|---|---|
| Full Docker-run Python regression | **58 tests, OK** | Unit/contract tests, not proof of entire browser UX |
| Authenticated Phase 7 smoke | **8/8 checks passed** | Health, auth, projects, DB backlog, delivery API, eligible stories, artifact statuses |
| Eligible backlog stories | **4/10** | `US-001`–`US-004`: clearance and PO approval; other six excluded |
| Solution Design artifact | **Approved** | Saved design; not an implemented attendance system |
| Implementation Plan artifact | **Approved; 12 tasks** | 4 design, 4 implementation, 4 testing |
| Dependency edges | **8** | Dependency references resolve in audit |
| Provisional estimation | **2 tasks need numeric estimates** | Team refinement required |
| Phase 7 artifact audit | **`passed: true`** | Content/schema/traceability checks; not semantic design certification |
| MCP discovery + tool call | **Passed** | Three tools discovered; preview `writes_performed: false` |
| Full backlog quality clearance | **Not passed** | Five review-required, one blocked/high finding |

The artifact audit confirms approved design/plan statuses, consistent eligible-story scope, architecture/component/API/entity fields, assumptions/open decisions, unique task keys, resolvable dependencies and estimation metadata. Its own limitations note that schema completeness **cannot establish semantic correctness** and it does not exercise state-changing approval endpoints or live publication.

## 9. Limitations and future scope

1. NFR-004 has no source-approved percentile, numeric response-time target or workload. Do not manufacture an SLA to clear the gate.
2. Ten generated stories are not ten approved stories; only four meet clearance **and** Product Owner approval. The five review-required items and one blocked item remain visible.
3. Six clarification proposals were approved earlier but no finalized fully quality-cleared backlog revision was established. Existing quality restrictions remain enforced.
4. The downstream design/planning agents are deterministic, traceable synthesis over saved upstream outputs, not autonomous LLM-led solution design or task negotiation. They require human technical review.
5. The proposed attendance architecture, APIs and data entities are candidate designs, not implemented student attendance functionality. Two task estimates await team refinement.
6. No claim is made of production-ready TLS/identity, load testing, multi-tenant security certification, or complete live integration regression against external providers.
7. A few earlier screenshots document intermediate UI states. Prefer the latest Phase 7 screenshots when presenting the demo.

## 10. Reproduction and reviewer quick start

**Prerequisites:** Docker Desktop/Compose, sufficient Ollama resources, browser, Python for local audits. Create private `.env` from `.env.example`; never commit real secrets. The repository includes synthetic BRD input and all migrations. Build and run with:

```cmd
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull qwen2.5:3b
```

Open `http://localhost:3000` and `http://localhost:8000/docs`. Create a local application user using the included CLI instructions. For an existing database, apply only missing migrations; **never run `docker compose down -v`** on your working project.

**Regression command (Cmder, project root):**

```cmd
docker compose run --rm --no-deps -e PYTHONPATH=/workspace:/workspace/backend:/app:/app/backend -v "%CD%:/workspace:ro" backend python -m unittest discover -s /workspace/tests -p "test_*.py" -v
```

**Read-only live verification (credentials passed only locally):**

```cmd
set REQFLOW_TEST_USER=YOUR_USER
set /p REQFLOW_TEST_PASSWORD=Password:
python scripts/phase7_live_smoke.py --project-id YOUR_PROJECT_ID --backlog-id YOUR_BACKLOG_ID
python scripts/phase7_final_evidence_audit.py --project-id YOUR_PROJECT_ID --backlog-id YOUR_BACKLOG_ID --output evidence/phase7_delivery_audit.json
set REQFLOW_TEST_PASSWORD=
```

**Read-only MCP demonstration:**

```cmd
docker compose exec -e PHASE6_ENABLE_TRUSTED_MCP=true -e PHASE6_TRUSTED_MCP_LIVE=false backend python /app/scripts/demo_mcp_client.py
```

For exact commands and API contracts, see the existing `docs/PHASE7_SCOPE_COMPLETION.md` and `docs/PHASE7_FINAL_VERIFICATION.md`.

## 11. Evidence gallery

All paths are relative to repository root. These real screenshots are stored under `data/screenshots/`:

| Evidence | File | Interpretation |
|---|---|---|
| Containers | [01-infrastructure-containers.png](../data/screenshots/01-infrastructure-containers.png) | Docker services |
| Ingestion | [05-document-indexing.png](../data/screenshots/05-document-indexing.png) | BRD indexed |
| RAG | [06-rag-search.png](../data/screenshots/06-rag-search.png) | Retrieved document chunks |
| Analysis | [07-requirements-analysis.png](../data/screenshots/07-requirements-analysis.png) | Extracted requirements |
| Backlog | [08-generated-backlog.png](../data/screenshots/08-generated-backlog.png) | Stories/AC |
| Quality | [09-quality-gate-evaluation.png](../data/screenshots/09-quality-gate-evaluation.png) | Partial quality clearance |
| GitHub/Jira | [10-github-issue.png](../data/screenshots/10-github-issue.png), [11-jira-issue.png](../data/screenshots/11-jira-issue.png) | Earlier live provider integration |
| Design | [12-design-overview.png](../data/screenshots/12-design-overview.png), [13-design-api-entities.png](../data/screenshots/13-design-api-entities.png), [14-design-traceability.png](../data/screenshots/14-design-traceability.png) | Proposed architecture/data/AC |
| Plan | [15-implementation-plan-overview.png](../data/screenshots/15-implementation-plan-overview.png)–[18-implementation-plan-summary.png](../data/screenshots/18-implementation-plan-summary.png) | 12 tasks, dependencies |
| MCP | [19-mcp-discovery.png](../data/screenshots/19-mcp-discovery.png), [20-mcp-dry-run.png](../data/screenshots/20-mcp-dry-run.png) | Actual stdio client discovery/preview |
| Runtime | [21-live-smoke-test.png](../data/screenshots/21-live-smoke-test.png) | 8 checks passed |
| Audit | [22-artifact-audit.png](../data/screenshots/22-artifact-audit.png) | `passed: true` |
| Regression | [23-unit-tests.png](../data/screenshots/23-unit-tests.png) | 58 tests OK |

## 12. Submission inventory

The final ZIP includes application source, Docker configuration, database migrations, synthetic BRD, tests, scripts, the original phase-specific guides, this final report, and the user-supplied evidence screenshots in `data/screenshots/`. It omits `.env`, `node_modules`, `.venv`, local DB dumps, runtime uploads, credentials and actual database volume data. **The ZIP does not include live PostgreSQL records**; screenshots and audit output prove the observed local run, while the sample BRD supports reproducibility.

**Suggested demonstration order:** Docker/health → BRD ingestion/RAG → requirements analysis → story generation/quality gate → four approved stories → generated design → human approval → implementation plan → human approval → MCP preview → 58 tests and audit → known limitations.
