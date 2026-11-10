# ReqFlow AI — Submission Contents

This archive contains the complete ReqFlow AI capstone source and supporting documentation.

## Contents

- `README.md` — project overview and final capstone report.
- `ReqFlow-AI-Final-Capstone-Report.pdf` — printable report.
- `docs/REQFLOW_IMPLEMENTATION_GUIDE.md` — consolidated technical implementation and verification reference for Phases 1–7.
- `data/screenshots/` — original screenshots of project runs, integration outputs, and test evidence.
- `evidence/phase7_delivery_audit.json` — captured read-only delivery artifact audit.
- `backend/`, `frontend/`, `agents/`, `integrations/`, `mcp_servers/` — runnable application and workflow source.
- `database/init/` — schema and additive migrations (001–009).
- `tests/` and `scripts/` — regression, smoke, integration and submission checks.
- `.env.example` — configuration template without secrets.

## Validation

Run `python scripts/phase7_submission_check.py --root . --mode submission` from the extracted directory.

Unit tests require the backend Python dependencies. The development documentation describes running the suite through Docker. The included screenshots and audit reflect recorded runs; they do not substitute for an independent production-security review.

## Boundaries

The attendance-management BRD is synthetic. Four of ten generated stories were quality-cleared and approved for the demonstrated delivery workflow; other stories remain under review or blocked. Design APIs and estimates are proposals, not a deployed attendance application.

Database dumps, active `.env` settings, user uploads, runtime caches, and installed dependencies are excluded.
