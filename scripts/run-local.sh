#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
ENV_FILE="$ROOT_DIR/.env"
BACKEND_LOG="$ROOT_DIR/.run-backend.log"
FRONTEND_LOG="$ROOT_DIR/.run-frontend.log"
BACKEND_PID=""
FRONTEND_PID=""

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Copy .env.example to .env and fill in the required values first."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required."
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-45}"
  local i

  for ((i = 1; i <= attempts; i += 1)); do
    if curl --silent --fail "$url" >/dev/null 2>&1; then
      echo "$label is ready: $url"
      return 0
    fi
    sleep 2
  done

  echo "$label did not become ready: $url"
  return 1
}

print_backend_failure_context() {
  echo
  echo "Backend failed to start. Recent backend log output:"
  if [[ -f "$BACKEND_LOG" ]]; then
    tail -n 40 "$BACKEND_LOG" || true
  else
    echo "No backend log file found."
  fi
  echo
  echo "Most common cause: DATABASE_URL in .env does not match your local PostgreSQL user/password/database."
  echo "You can initialize a matching local database with:"
  echo "  ./scripts/setup-local-postgres.sh"
}

trap cleanup EXIT INT TERM

echo "Preparing backend virtual environment..."
if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  python3 -m venv "$BACKEND_DIR/.venv"
fi

"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt" >/dev/null

echo "Installing frontend dependencies..."
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  (cd "$FRONTEND_DIR" && npm install >/dev/null)
fi

echo "Starting backend..."
(
  cd "$BACKEND_DIR"
  source ".venv/bin/activate"
  exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

if ! wait_for_http "$BACKEND_URL/health" "Backend"; then
  print_backend_failure_context
  exit 1
fi

echo "Running refresh job once for local testing..."
curl --silent --show-error --fail -X POST "$BACKEND_URL/jobs/refresh-events" >/dev/null

TODAY_VANCOUVER="$(
  TZ=America/Vancouver date +%F
)"

echo "Verifying events endpoint for $TODAY_VANCOUVER..."
curl --silent --show-error --fail "$BACKEND_URL/events?date=$TODAY_VANCOUVER" >/dev/null

echo "Starting frontend..."
(
  cd "$FRONTEND_DIR"
  export BACKEND_URL="$BACKEND_URL"
  exec npm run dev
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

wait_for_http "$FRONTEND_URL" "Frontend"

echo
echo "App is running."
echo "Frontend: $FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
echo "Backend log:  $BACKEND_LOG"
echo "Frontend log: $FRONTEND_LOG"
echo
echo "Press Ctrl+C to stop both services."

wait "$BACKEND_PID" "$FRONTEND_PID"
