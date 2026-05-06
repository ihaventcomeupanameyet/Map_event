#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_ENV_FILE="$ROOT_DIR/.env.docker"

if [[ ! -f "$DOCKER_ENV_FILE" ]]; then
  echo "Missing $DOCKER_ENV_FILE"
  echo "Copy .env.docker.example to .env.docker and fill in TICKETMASTER_API_KEY first."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "docker compose or docker-compose is required."
  exit 1
fi

cd "$ROOT_DIR"
"${COMPOSE_CMD[@]}" --env-file "$DOCKER_ENV_FILE" up
