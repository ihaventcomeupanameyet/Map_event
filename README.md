
# Vancouver Event Discovery Map

Purpose

This project is an MVP that discovers public events around Vancouver and displays them on an interactive map. It fetches events from third-party providers, normalizes and stores them, and exposes a backend API consumed by a Next.js frontend with map-based UI.

What it does

- Periodically fetches events from providers (Ticketmaster, Eventbrite, SeatGeek).
- Normalizes event data and stores it in PostgreSQL.
- Provides a FastAPI JSON API for event search and details (`/events`, `/health`, etc.).
- Renders an interactive map UI (Leaflet) in a Next.js frontend that queries the backend.

This repository contains:

- `backend/` — FastAPI app, SQLAlchemy models, and background jobs
- `frontend/` — Next.js app and React components
- `docker-compose.yml` / `docker-compose.production.yml` — local and production stacks
- `scripts/ec2-user-data.sh` — user-data for provisioning an EC2 instance (installs Docker, fetches `.env` from SSM or accepts an embedded `ENV_B64`, and runs the production compose)
- `scripts/aws-ec2-bootstrap.sh` — alternative bootstrap script to install system packages and configure systemd services (non-Docker path)
- `DEPLOY.md` — focused EC2 deployment instructions (user-data, SSM, ECR, Terraform examples)
- `.env.production.example` — production environment variables to populate

Quick start (development)

1. Copy `.env.example` to `.env` and fill in API keys and `DATABASE_URL`.
2. Start services locally:

```bash
# backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend (new terminal)
cd frontend
npm install
npm run dev
```

Deploy to EC2 (no SSH required)

The repo includes `scripts/ec2-user-data.sh` which supports three ways to provide a `.env` to the instance:

- `ENV_B64` (preferred for quick deploy): base64-encoded `.env` embedded in user-data
- `ENV_PLAIN`: plain-text `.env` in user-data (less secure)
- `SSM_PARAM`: name of an SSM SecureString parameter that contains the `.env` (recommended)

See `DEPLOY.md` for step-by-step commands to create the SSM parameter, prepare `user-data`, and launch the instance with an instance profile that allows `ssm:GetParameter`.

Security notes

- Do not commit secrets to the repo. Use SSM Parameter Store or Secrets Manager.
- Prefer CI (GitHub Actions) -> ECR -> EC2 pulls for production immutability.

If you want a ready-to-launch `user-data` that embeds your `.env.production.example` as `ENV_B64`, or a GitHub Actions workflow that builds and pushes images to ECR, ask and I will generate them.

