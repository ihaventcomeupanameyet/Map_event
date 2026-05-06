You are working in a sandbox on a new MVP project.

Project goal:
Build a Vancouver event discovery map app. Users select a date, the frontend queries the backend, and events for that date are shown as pins on a Leaflet map.

Tech stack:
Frontend:
- Next.js
- TypeScript
- Tailwind
- Leaflet
- No auth for MVP
- No Google Maps / Mapbox

Backend:
- Python FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- PostgreSQL runs on the same AWS EC2 instance as backend. Do NOT use RDS.
- Use EBS-backed EC2 storage for PostgreSQL persistence.

Data source:
- Ticketmaster Discovery API
- City/area: Vancouver, BC
- Fetch events for the next 30 days
- Store normalized event data in PostgreSQL as cache

Event model:
{
  id: string,                 // internal id or source-prefixed id
  source: "ticketmaster",
  sourceEventId: string,      // Ticketmaster event.id
  name: string,
  startTime: string,          // ISO datetime
  endTime?: string,
  venueName: string,
  address?: string,
  lat: number,
  lng: number,
  organizer?: string,
  description?: string,
  category?: string,
  ticketUrl: string,
  imageUrl?: string
}

Database rules:

- Use a synthetic primary key.
- Add UNIQUE(source, source_event_id) to prevent duplicates.
- Use upsert when refreshing data.
- Do not blindly insert duplicates.
- Store last_seen_at.
- Remove expired events from db during refresh:
  - If endTime exists, event is expired when endTime < now
  - Else if startTime exists, event is expired when startTime < now
  - Else if only date exists, event is expired when date < today
- Do not wipe the whole database before fetching.

Use a combined string primary key for events:id = source + ":" + source_event_idsource_event_id is the event id provided by the external API.This avoids collisions when different data sources return the same event id.Example:ticketmaster:abc123ubc:abc123Still store source and source_event_id as separate columns for debugging/querying, but the primary key should be the combined id string.


Backend requirements:
- Provide API endpoint:
  GET /events?date=YYYY-MM-DD
  It should query PostgreSQL and return events for that date.
- Provide a manual refresh endpoint for development:
  POST /jobs/refresh-events
  It should fetch Ticketmaster events for the next 30 days and upsert them.
- On backend startup, if the events table is empty, perform a one-time refresh.
- Add a scheduled job that runs every night at 1 AM server time.
- The job must:
  - fetch Ticketmaster events for the next 30 days
  - upsert events into PostgreSQL
  - update existing events if data changed
  - insert new events if they do not exist
  - remove expired events
- The scheduled job can use APScheduler for MVP.
- Keep the refresh logic in a separate service/module, not inside route handlers.
- Use environment variables for API keys and database URL.

Frontend requirements:
- Default date is today.
- Add a date selector/calendar input.
- Query backend /events?date=YYYY-MM-DD when date changes.
- Render returned events as Leaflet pins using lat/lng.
- Popup should show:
  - event name
  - venue name
  - start time
  - category if available
  - link to the original event page, such as Ticketmaster event.url
- Initialize Leaflet map only once.
- Do not recreate the map on every render.
- Do not duplicate markers.
- Clear old markers when events change.
- Use dynamic import for Leaflet if needed to avoid Next.js SSR window errors.
- Use refs instead of document.getElementById.

Map setup:
- Use Leaflet.
- Use OpenStreetMap tile layer for development:
  https://tile.openstreetmap.org/{z}/{x}/{y}.png
- Include attribution.
- Center map on Vancouver:
  lat: 49.2827
  lng: -123.1207
  zoom: 12

Project files:
- Create frontend and backend folders if needed.
- Add .env.example with:
  TICKETMASTER_API_KEY=
  DATABASE_URL=
  BACKEND_URL=
- Add DEPLOY.md explaining:
  - how to run locally
  - how to set env vars
  - how to run PostgreSQL on EC2
  - how to start backend
  - how to start frontend
  - how the nightly job works
  - how EBS persistence should be handled conceptually

Important constraints:
- Keep MVP simple.
- Do not add authentication.
- Do not add payments.
- Do not add user accounts.
- Do not add RDS.
- Do not redesign into microservices.
- Do not add Docker unless necessary; if using Docker, keep it minimal.
- Prefer clear code over clever abstractions.
- Add comments where architecture matters.
- After implementation, summarize changed files and how to run the app.

Before writing code:
1. Inspect the current project structure.
2. Propose a concise implementation plan.
3. Then implement.