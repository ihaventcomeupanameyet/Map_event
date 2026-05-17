#!/usr/bin/env bash

set -euo pipefail

# Simple EC2 user-data script to provision an Ubuntu instance, clone the repo,
# fetch an env file from SSM (optional), install Docker, and run docker compose.
# Usage: pass `REPO_URL` and optionally `SSM_PARAM` via EC2 user-data or metadata.

REPO_URL="${REPO_URL:-https://github.com/your-org/your-repo.git}"
APP_DIR="${APP_DIR:-/opt/map_event_app}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
SSM_PARAM="${SSM_PARAM:-/map_event_app/.env}"
ECR_REGISTRY="${ECR_REGISTRY:-}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "This script must be run as root"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release git jq || true

# Install Docker if missing
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

# Ensure docker compose plugin is available
if ! docker compose version >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker-compose-plugin || true
fi

# Install AWS CLI if not present (needed for SSM/ECR actions)
if ! command -v aws >/dev/null 2>&1; then
  apt-get update
  apt-get install -y awscli || (apt-get install -y python3-pip && pip3 install --no-cache-dir awscli)
fi

# Create application directory and clone or update repo
if [[ ! -d "$APP_DIR" ]]; then
  mkdir -p "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
else
  cd "$APP_DIR"
  if [[ -d .git ]]; then
    git fetch --all --prune
    git reset --hard origin/HEAD || true
  else
    rm -rf "$APP_DIR" && git clone "$REPO_URL" "$APP_DIR"
  fi
fi

# Support writing an embedded env into the application directory.
# Priority: ENV_B64 -> ENV_PLAIN -> SSM parameter
if [[ -n "${ENV_B64:-}" ]]; then
  echo "$ENV_B64" | base64 --decode >"$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Wrote env from ENV_B64 to $APP_DIR/.env"
elif [[ -n "${ENV_PLAIN:-}" ]]; then
  echo "$ENV_PLAIN" >"$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Wrote env from ENV_PLAIN to $APP_DIR/.env"
else
  # Attempt to fetch a prebuilt .env from SSM Parameter Store (SecureString)
  if aws ssm get-parameter --name "$SSM_PARAM" --with-decryption >/dev/null 2>&1; then
    aws ssm get-parameter --name "$SSM_PARAM" --with-decryption --query Parameter.Value --output text >"$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "Wrote env from SSM to $APP_DIR/.env"
  else
    echo "SSM parameter $SSM_PARAM not found; ensure $APP_DIR/.env exists or set SSM_PARAM or ENV_B64/ENV_PLAIN"
  fi
fi

cd "$APP_DIR"

# If using ECR-hosted images, login to ECR (instance must have permissions)
if [[ -n "$ECR_REGISTRY" ]]; then
  aws ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY"
fi

# Start the app with docker compose (production compose file by default)
docker compose -f "$COMPOSE_FILE" pull || true
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Deployment complete. Docker compose status:"
docker compose -f "$COMPOSE_FILE" ps || true

exit 0
