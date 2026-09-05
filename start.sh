#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
FRONTEND_DIR="$ROOT_DIR/frontend"
FRONTEND_URL="http://localhost:5173/"
FRONTEND_PID=""
STARTED_BACKEND=0
STARTED_POSTGRES=0
STARTED_SIMULATOR=0
SIMULATION_INTERVAL_SECONDS="${SIMULATION_INTERVAL_SECONDS:-30}"
export SIMULATION_INTERVAL_SECONDS
[[ "$SIMULATION_INTERVAL_SECONDS" =~ ^[1-9][0-9]*$ ]] || {
  printf 'SIMULATION_INTERVAL_SECONDS must be a positive integer.\n' >&2
  exit 1
}
for data_file in data/demo_catalog.json data/scenarios/historical_baseline_57.json data/scenarios/historical_update_57.json; do
  [[ -f "$ROOT_DIR/$data_file" ]] || { printf 'Missing saved demo file: %s\n' "$data_file" >&2; exit 1; }
done

log() {
  printf '[start] %s\n' "$*"
}

cleanup() {
  local exit_code=$?
  trap - INT TERM EXIT
  set +e

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Stopping frontend (pid $FRONTEND_PID)..."
    kill "$FRONTEND_PID" 2>/dev/null
    wait "$FRONTEND_PID" 2>/dev/null
  fi
  FRONTEND_PID=""

  if [[ "$STARTED_BACKEND" == "1" || "$STARTED_POSTGRES" == "1" || "$STARTED_SIMULATOR" == "1" ]]; then
    local services=()
    [[ "$STARTED_BACKEND" == "1" ]] && services+=(backend)
    [[ "$STARTED_POSTGRES" == "1" ]] && services+=(postgres)
    [[ "$STARTED_SIMULATOR" == "1" ]] && services+=(market-ingestion)
    log "Stopping Compose services started by this command: ${services[*]}"
    (cd "$ROOT_DIR" && docker compose stop "${services[@]}")
  fi

  exit "$exit_code"
}

trap cleanup EXIT
trap 'exit 130' INT TERM

command -v docker >/dev/null 2>&1 || { printf 'Docker is required.\n' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { printf 'npm is required.\n' >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { printf 'curl is required.\n' >&2; exit 1; }
[[ -f "$FRONTEND_DIR/package.json" ]] || { printf 'Missing frontend/package.json.\n' >&2; exit 1; }

docker compose version >/dev/null 2>&1 || { printf 'Docker Compose is required.\n' >&2; exit 1; }

if [[ -z "$(docker compose ps --status running -q postgres 2>/dev/null)" ]]; then
  STARTED_POSTGRES=1
fi
if [[ -z "$(docker compose ps --status running -q backend 2>/dev/null)" ]]; then
  STARTED_BACKEND=1
fi

log "Starting PostgreSQL and backend with Docker Compose..."
docker compose up -d --build postgres backend

log "Waiting for the backend health endpoint..."
backend_ready=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 1 "http://localhost:8000/health" >/dev/null 2>&1; then
    backend_ready=1
    break
  fi
  sleep 1
done

if [[ "$backend_ready" != "1" ]]; then
  printf 'Backend did not respond at http://localhost:8000/health within 60 seconds.\n' >&2
  exit 1
fi

log "Applying database migrations..."
docker compose exec -T backend alembic upgrade head

log "Ensuring the instrument catalog exists..."
docker compose exec -T backend env PYTHONPATH=/app python -c '
import asyncio
from app.seed import ensure_instruments_exist

inserted = asyncio.run(ensure_instruments_exist())
print(f"Instrument catalog ready ({inserted} new rows).")
'

# Stop any existing worker before resetting the simulated database.
docker compose stop market-ingestion

log "Preparing deterministic historical demo data..."
docker compose exec -T backend env PYTHONPATH=/app python scripts/reset_demo_state.py
docker compose exec -T backend env PYTHONPATH=/app \
  python -m app.workers.historical_replay \
  data/scenarios/historical_baseline_57.json
docker compose exec -T backend env PYTHONPATH=/app \
  python -m app.workers.historical_replay \
  data/scenarios/historical_update_57.json \
  --rebase-to-now
docker compose exec -T backend env PYTHONPATH=/app python -c '
from sqlalchemy import update
from app.db import AsyncSessionLocal
from app.models import Watchlist
import asyncio

async def reset_boundaries():
    async with AsyncSessionLocal() as db:
        await db.execute(update(Watchlist).values(last_viewed_at=None))
        await db.commit()

asyncio.run(reset_boundaries())
'
log "Starting historical simulation every ${SIMULATION_INTERVAL_SECONDS}s..."
STARTED_SIMULATOR=1
docker compose up -d --build market-ingestion
log "Historical demo ready; saved prices will repeat in scenario order."

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "Installing frontend dependencies..."
  (
    cd "$FRONTEND_DIR"
    if [[ -f package-lock.json ]]; then
      npm ci --no-audit --no-fund
    else
      npm install --no-audit --no-fund
    fi
  )
fi

if curl -fsS --max-time 1 "$FRONTEND_URL" >/dev/null 2>&1; then
  log "Frontend already responding at $FRONTEND_URL; not starting a duplicate."
else
  log "Starting Vite frontend..."
  (
    cd "$FRONTEND_DIR"
    exec npm run dev -- --host 0.0.0.0
  ) &
  FRONTEND_PID=$!

  ready=0
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 1 "$FRONTEND_URL" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done

  if [[ "$ready" != "1" ]]; then
    printf 'Frontend did not respond at %s within 60 seconds.\n' "$FRONTEND_URL" >&2
    exit 1
  fi
  log "Frontend is responding at $FRONTEND_URL"
fi

if command -v open >/dev/null 2>&1; then
  open "$FRONTEND_URL" >/dev/null 2>&1 || log "Could not open the browser automatically."
else
  log "The macOS open command is unavailable; open $FRONTEND_URL manually."
fi

log "Demo is running at $FRONTEND_URL"
log "Press Ctrl+C to stop processes started by this command."

if [[ -n "$FRONTEND_PID" ]]; then
  wait "$FRONTEND_PID"
else
  while :; do
    sleep 3600
  done
fi
