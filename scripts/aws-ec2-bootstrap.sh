#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this script as root on the EC2 instance."
  exit 1
fi

APP_USER="${APP_USER:-ubuntu}"
APP_DIR="${APP_DIR:-/opt/map_event_app}"
POSTGRES_DATA_DIR="${POSTGRES_DATA_DIR:-/var/lib/postgresql-data}"
POSTGRES_DB="${POSTGRES_DB:-map_event_app}"
POSTGRES_APP_USER="${POSTGRES_APP_USER:-map_event_app}"
POSTGRES_APP_PASSWORD="${POSTGRES_APP_PASSWORD:-change-me}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
NODE_MAJOR="${NODE_MAJOR:-20}"
ENV_FILE="$APP_DIR/.env"

if [[ "$POSTGRES_APP_PASSWORD" == "change-me" ]]; then
  echo "Set POSTGRES_APP_PASSWORD before running this script."
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing application directory: $APP_DIR"
  echo "Copy the repo to the EC2 instance before running this script."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Create it from .env.example before running this script."
  exit 1
fi

apt-get update
apt-get install -y curl ca-certificates gnupg lsb-release python3 python3-venv python3-pip postgresql postgresql-contrib nginx

if [[ ! -f /etc/apt/keyrings/nodesource.gpg ]]; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
fi

cat >/etc/apt/sources.list.d/nodesource.list <<EOF
deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main
EOF

apt-get update
apt-get install -y nodejs

PG_VERSION="$(ls /usr/lib/postgresql | sort -V | tail -n 1)"
PG_BIN_DIR="/usr/lib/postgresql/$PG_VERSION/bin"
PG_CONF="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
PG_HBA="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"

install -d -o postgres -g postgres "$POSTGRES_DATA_DIR"

if [[ ! -f "$POSTGRES_DATA_DIR/PG_VERSION" ]]; then
  sudo -u postgres "$PG_BIN_DIR/initdb" -D "$POSTGRES_DATA_DIR"
fi

sed -i "s|^data_directory = .*|data_directory = '$POSTGRES_DATA_DIR'|" "$PG_CONF"
sed -i "s/^#listen_addresses =.*/listen_addresses = '127.0.0.1'/" "$PG_CONF"

if ! grep -q "^host[[:space:]]\+$POSTGRES_DB[[:space:]]\+$POSTGRES_APP_USER[[:space:]]\+127.0.0.1/32[[:space:]]\+md5" "$PG_HBA"; then
  printf "\nhost %s %s 127.0.0.1/32 md5\n" "$POSTGRES_DB" "$POSTGRES_APP_USER" >>"$PG_HBA"
fi

systemctl enable postgresql
systemctl restart postgresql

sudo -u postgres psql <<EOF
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$POSTGRES_APP_USER') THEN
    CREATE ROLE $POSTGRES_APP_USER LOGIN PASSWORD '$POSTGRES_APP_PASSWORD';
  ELSE
    ALTER ROLE $POSTGRES_APP_USER WITH LOGIN PASSWORD '$POSTGRES_APP_PASSWORD';
  END IF;
END
\$\$;
EOF

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'" | grep -q 1 || sudo -u postgres createdb -O "$POSTGRES_APP_USER" "$POSTGRES_DB"

python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

(cd "$APP_DIR/frontend" && npm install && npm run build)

chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

cat >/etc/systemd/system/map-event-backend.service <<EOF
[Unit]
Description=Map Event Backend
After=network.target postgresql.service

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/map-event-frontend.service <<EOF
[Unit]
Description=Map Event Frontend
After=network.target map-event-backend.service

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR/frontend
EnvironmentFile=$ENV_FILE
Environment=PORT=$FRONTEND_PORT
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/nginx/sites-available/map_event_app <<EOF
server {
    listen 80 default_server;
    server_name _;

    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:$FRONTEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/map_event_app /etc/nginx/sites-enabled/map_event_app
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable map-event-backend.service map-event-frontend.service nginx
systemctl restart map-event-backend.service
systemctl restart map-event-frontend.service
systemctl restart nginx

cat <<EOF
Bootstrap complete.

What this script handled:
- installed Python, PostgreSQL, Node.js, and Nginx
- initialized PostgreSQL and created the app database/user
- installed backend/frontend dependencies
- built the Next.js frontend
- created systemd services for backend and frontend
- configured Nginx to proxy / to the frontend and /api/ to the backend

What you still need to verify manually:
- your EBS volume is attached, mounted, and intended for $POSTGRES_DATA_DIR
- security groups allow ports 80 and 22 as needed
- the .env file at $ENV_FILE has the correct TICKETMASTER_API_KEY, BACKEND_URL, and DATABASE_URL

Suggested DATABASE_URL:
postgresql+asyncpg://$POSTGRES_APP_USER:$POSTGRES_APP_PASSWORD@localhost:5432/$POSTGRES_DB
EOF
