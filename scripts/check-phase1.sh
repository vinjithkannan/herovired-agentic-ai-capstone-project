#!/usr/bin/env sh
set -eu
curl -fsS http://localhost:8000/health
echo
curl -fsS http://localhost:8000/api/v1/system/info
echo
docker compose exec -T postgres psql -U reqflow -d reqflow -c "SELECT extname FROM pg_extension WHERE extname='vector';"
docker compose exec -T redis redis-cli ping
echo "Phase 1 smoke checks completed."
