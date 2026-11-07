# Phase 1 smoke tests

| ID | Test | Expected |
|---|---|---|
| P1-001 | Open frontend at port 3000 | Dashboard loads |
| P1-002 | GET `/health` | HTTP 200 and status `ok` |
| P1-003 | GET `/api/v1/system/info` | Phase 1 component information |
| P1-004 | Query `pg_extension` for vector | Extension exists |
| P1-005 | Redis `PING` | `PONG` |
| P1-006 | Restart backend container | Backend recovers |
