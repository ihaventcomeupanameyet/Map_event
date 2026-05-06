#!/usr/bin/env bash

set -euo pipefail

APP_DB="${APP_DB:-map_event_app}"
APP_USER="${APP_USER:-map_event_app}"
APP_PASSWORD="${APP_PASSWORD:-map_event_app}"
APP_HOST="${APP_HOST:-localhost}"
APP_PORT="${APP_PORT:-5432}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required."
  exit 1
fi

if ! command -v createdb >/dev/null 2>&1; then
  echo "createdb is required."
  exit 1
fi

if ! command -v createuser >/dev/null 2>&1; then
  echo "createuser is required."
  exit 1
fi

if ! pg_isready -h "$APP_HOST" -p "$APP_PORT" >/dev/null 2>&1; then
  echo "PostgreSQL is not accepting connections on $APP_HOST:$APP_PORT"
  echo "Start PostgreSQL first, then rerun this script."
  exit 1
fi

echo "Configuring PostgreSQL role: $APP_USER"
if ! psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$APP_USER'" | grep -q 1; then
  createuser "$APP_USER"
fi

psql postgres -c "ALTER ROLE \"$APP_USER\" WITH LOGIN PASSWORD '$APP_PASSWORD';" >/dev/null

echo "Configuring PostgreSQL database: $APP_DB"
if ! psql postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$APP_DB'" | grep -q 1; then
  createdb -O "$APP_USER" "$APP_DB"
fi

cat <<EOF
Local PostgreSQL setup complete.

Use this DATABASE_URL in .env:
DATABASE_URL=postgresql+asyncpg://$APP_USER:$APP_PASSWORD@$APP_HOST:$APP_PORT/$APP_DB

If your PostgreSQL server uses peer auth for local admin access, run this script as the OS user that can manage PostgreSQL.
EOF
