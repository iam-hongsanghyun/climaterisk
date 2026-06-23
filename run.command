#!/usr/bin/env bash
# climaterisk launcher — starts the orchestration backend (FastAPI/uvicorn) and
# the frontend (Vite), waits for the backend to be healthy, then opens the app.
# The CLIMADA worker (Phase 2) runs on demand as a separate conda subprocess;
# this script only checks whether its env is present.
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present (export each KEY=VALUE).
if [ -f .env ]; then set -a; . ./.env; set +a; fi

BACKEND_HOST="${CLIMATERISK_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${CLIMATERISK_BACKEND_PORT:-8099}"
FRONTEND_HOST="localhost"
FRONTEND_PORT="${CLIMATERISK_FRONTEND_PORT:-5174}"
FRONTEND_DIR="frontend/climaterisk"
# Project-local CLIMADA conda (prefix) env — never a global/named env.
WORKER_ENV_DIR="${CLIMATERISK_WORKER_ENV_DIR:-.climada-env}"
export CLIMATERISK_BACKEND_PORT CLIMATERISK_FRONTEND_PORT

cleanup() { echo; echo "▶ shutting down…"; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "▶ stopping any previous climaterisk servers…"
for port in "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  [ -n "${pids}" ] && kill ${pids} 2>/dev/null || true
done
pkill -f "uvicorn climaterisk.api.main:app" 2>/dev/null || true
sleep 0.5

if [ ! -d ".venv" ]; then
  echo "▶ installing backend deps (uv sync)…"
  uv sync --all-extras
fi
if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
  echo "▶ installing frontend deps (npm install)…"
  ( cd "${FRONTEND_DIR}" && npm install )
fi

# Soft check: is the project-local CLIMADA worker env present? (Non-fatal — only Phase 2.)
if [ -x "${WORKER_ENV_DIR}/bin/python" ]; then
  echo "▶ CLIMADA worker env '${WORKER_ENV_DIR}' ✓"
else
  echo "▶ CLIMADA worker env '${WORKER_ENV_DIR}' not found — physical-risk runs (Phase 2) unavailable."
  echo "  build it: conda env create -f worker/climaterisk_worker/env_climada.yml --prefix ./${WORKER_ENV_DIR}"
fi

echo "▶ backend  → http://${BACKEND_HOST}:${BACKEND_PORT}"
# --reload-dir src: watch ONLY backend source. Watching the repo root makes uvicorn
# reload on every SQLite-WAL write under data/ (one per status poll), which orphans
# in-flight worker subprocesses and leaves runs stuck polling "running" forever.
uv run uvicorn climaterisk.api.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" \
  --reload --reload-dir src &

echo "▶ frontend → http://${FRONTEND_HOST}:${FRONTEND_PORT}"
( cd "${FRONTEND_DIR}" && npm run dev -- --port "${FRONTEND_PORT}" ) &

echo -n "▶ waiting for backend"
for _ in $(seq 1 60); do
  if curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    echo " ✓"; break
  fi
  echo -n "."; sleep 0.5
done

URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"
sleep 2
if command -v open >/dev/null 2>&1; then open "${URL}"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "${URL}"; fi
echo "▶ open ${URL} (Ctrl-C to stop)"

wait
