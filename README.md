
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

