# Deploy and Run

## Local development

1. Copy `.env.example` to `.env` and fill in:
   - `TICKETMASTER_API_KEY`
   - `DATABASE_URL`
   - `BACKEND_URL`
2. Start PostgreSQL locally and create a database named `map_event_app`.
   To create a matching local role/database quickly:
   ```bash
   chmod +x scripts/setup-local-postgres.sh
   ./scripts/setup-local-postgres.sh
   ```
3. Start the backend:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
4. Start the frontend in a second terminal:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
5. Open `http://localhost:3000`.

### Quick local script

To bootstrap and run both services together:

```bash
chmod +x scripts/run-local.sh
./scripts/run-local.sh
```

The script will:

- verify `.env` exists
- create `backend/.venv` if needed
- install backend requirements
- install frontend dependencies if `node_modules` is missing
- start backend and frontend
- call `POST /jobs/refresh-events`
- verify `/health`, `/events`, and the frontend home page

Logs are written to `.run-backend.log` and `.run-frontend.log` in the repo root.
If backend startup fails, the script now prints the recent backend log and points to the PostgreSQL setup helper.

## Docker development

If you prefer a Docker-based setup closer to your existing workflow:

1. Copy `.env.docker.example` to `.env.docker`.
2. Fill in `TICKETMASTER_API_KEY`.
3. Start the stack:
   ```bash
   chmod +x scripts/run-docker.sh
   ./scripts/run-docker.sh
   ```

This starts three containers:

- `db`: PostgreSQL 16
- `backend`: FastAPI on `http://localhost:8000`
- `frontend`: Next.js on `http://localhost:3000`

This Docker setup is now development-oriented:

- frontend source is bind-mounted into the container
- backend source is bind-mounted into the container
- frontend keeps `node_modules` and `.next` inside Docker-managed volumes
- backend runs `uvicorn --reload`
- frontend runs `next dev`

That means normal source edits should show up without rebuilding the images.

The Docker env file uses these keys:

- `TICKETMASTER_API_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `BACKEND_URL`
- `GEOCODER_BASE_URL`
- `GEOCODER_USER_AGENT`
- `GEOCODER_MIN_INTERVAL_SECONDS`

The default Docker `DATABASE_URL` points at the Compose service name `db`, not `localhost`.
The geocoder defaults target Nominatim and are only used when Ticketmaster venue coordinates are missing or invalid.

If you change dependency manifests such as `frontend/package.json`, `frontend/package-lock.json`, or `backend/requirements.txt`, restart the containers. You only need a rebuild when the Docker image itself must change, such as a base image or Dockerfile change.

## Docker production

For a small EC2 deployment, use the production-specific files instead of the dev stack:

1. Copy `.env.production.example` to `.env.production`.
2. Fill in the real values, especially:
   - `TICKETMASTER_API_KEY`
   - `POSTGRES_PASSWORD`
   - `DATABASE_URL`
   - `BACKEND_URL`
3. Build and start:
   ```bash
   docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
   ```

Production files:

- `backend/Dockerfile.production`
- `frontend/Dockerfile.production`
- `docker-compose.production.yml`

These are intentionally leaner than the dev stack:

- frontend builds as a Next.js standalone server
- backend runs a single Uvicorn worker
- no bind mounts or live reload
- PostgreSQL memory is tuned down for a small instance
- service memory limits are set for a roughly 1 GB host budget

Practical note for a `t4g.micro` or `t4.micro`-class instance with 1 GiB RAM:

- this setup is about as small as you should run it
- enable swap on the EC2 instance to reduce OOM risk during spikes or refresh jobs
- avoid running other memory-heavy services on the same machine
- if usage grows, increase instance size before adding more workers

## Environment variables

- `TICKETMASTER_API_KEY`: Ticketmaster Discovery API key.
- `DATABASE_URL`: PostgreSQL SQLAlchemy async URL. Example:
  `postgresql+asyncpg://map_event_app:map_event_app@localhost:5432/map_event_app`
- `BACKEND_URL`: Backend base URL used by the frontend. Example:
  `http://localhost:8000`

## PostgreSQL on EC2

Run PostgreSQL on the same EC2 instance as the FastAPI app for this MVP.

- Install PostgreSQL directly on the instance.
- Store the PostgreSQL data directory on an attached EBS volume.
- Mount the EBS volume on boot and point PostgreSQL storage to that mounted path.
- Restrict inbound access so PostgreSQL is not publicly exposed unless you explicitly need admin access.
- Keep app and database on the same host and connect through the local network interface.

### EC2 bootstrap helper

You can automate part of the instance setup with:

```bash
chmod +x scripts/aws-ec2-bootstrap.sh
sudo APP_DIR=/opt/map_event_app POSTGRES_APP_PASSWORD='replace-this' ./scripts/aws-ec2-bootstrap.sh
```

This helper is intentionally scoped to bootstrapping an Ubuntu EC2 instance after you have already:

- launched the EC2 instance
- attached and mounted your EBS volume
- copied the repo onto the machine
- created the app `.env`

It does not create EC2 instances, VPCs, security groups, or EBS volumes for you. Those can be scripted with the AWS CLI or Terraform, but that requires your AWS account/networking choices and is better handled as a separate infrastructure script rather than hidden inside app bootstrap logic.

## Backend startup

Use the backend service with:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

What happens on startup:

- SQLAlchemy creates the tables if they do not exist.
- APScheduler starts a nightly refresh job at `1:00 AM` server time.
- If the `events` table is empty, the app performs a one-time Ticketmaster refresh.

## Frontend startup

Use the frontend service with:

```bash
cd frontend
npm run build
npm run start
```

The frontend reads `BACKEND_URL` at build/runtime through Next.js config and uses it for `/events`.

## Nightly refresh job

The backend scheduler runs every night at `1:00 AM` server time.

The job:

- fetches Vancouver events for the next 30 days from Ticketmaster
- normalizes them into the app event model
- upserts by `id` and enforces `UNIQUE(source, source_event_id)`
- updates `last_seen_at`
- removes expired events without wiping the full table

For local development, you can trigger the same logic manually:

```bash
curl -X POST http://localhost:8000/jobs/refresh-events
```

## EBS persistence concept

For EC2 persistence, the EBS volume is the durable layer and the EC2 instance is the compute layer.

- Attach an EBS volume to the EC2 instance.
- Format and mount it to a stable path such as `/var/lib/postgresql-data`.
- Configure PostgreSQL to use that mounted path as its data directory.
- On instance replacement, reattach the EBS volume to the new EC2 host and remount it before starting PostgreSQL.
- Snapshot the EBS volume regularly if you want backup/recovery coverage.
