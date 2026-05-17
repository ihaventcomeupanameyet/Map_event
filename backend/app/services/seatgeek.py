from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.services.location import geocode_address, normalize_coordinates


SEATGEEK_EVENTS_PATH = "/events"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo("America/Vancouver"))
    return parsed


def _pick_image(raw_event: dict) -> str | None:
    performers = raw_event.get("performers") or []
    if not performers:
        return None

    primary = performers[0]
    images = primary.get("images") or {}
    return images.get("huge") or images.get("480x320") or primary.get("image")


async def fetch_seatgeek_events(
    client: httpx.AsyncClient,
    settings: Settings,
) -> list[dict]:
    if not settings.seatgeek_client_id:
        return []

    now = datetime.now(tz=ZoneInfo("UTC"))
    end = now + timedelta(days=settings.refresh_window_days)

    normalized_events: list[dict] = []
    geocode_cache: dict[str, tuple[float, float] | None] = {}
    geocode_state = {"last_request_at": 0.0}
    page = 1
    per_page = 100

    while True:
        params = {
            "client_id": settings.seatgeek_client_id,
            "venue.city": settings.events_city,
            "venue.state": "BC",
            "datetime_utc.gte": now.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S"),
            "datetime_utc.lte": end.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S"),
            "sort": "datetime_utc.asc",
            "per_page": per_page,
            "page": page,
        }
        if settings.seatgeek_client_secret:
            params["client_secret"] = settings.seatgeek_client_secret

        response = await client.get(
            f"{settings.seatgeek_base_url}{SEATGEEK_EVENTS_PATH}",
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()

        for raw_event in payload.get("events", []):
            venue = raw_event.get("venue") or {}
            if not venue:
                continue

            source_event_id = str(raw_event["id"])
            address_line = venue.get("address")
            city = venue.get("city")
            state = venue.get("state")
            postal_code = venue.get("postal_code")
            country_code = venue.get("country")
            country_name = "Canada" if country_code == "CA" else country_code

            location = venue.get("location") or {}
            coordinates = normalize_coordinates(
                location.get("lat"),
                location.get("lon"),
                country_code,
            )
            if coordinates is None:
                coordinates = await geocode_address(
                    client,
                    settings,
                    address_line=address_line,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    country=country_name,
                    country_code=country_code,
                    geocode_cache=geocode_cache,
                    geocode_state=geocode_state,
                )
                if coordinates is None:
                    continue
            latitude, longitude = coordinates

            start_time = _parse_datetime(raw_event.get("datetime_local") or raw_event.get("datetime_utc"))
            if start_time is None:
                continue
            event_date = start_time.astimezone(ZoneInfo("America/Vancouver")).date()

            category = None
            taxonomies = raw_event.get("taxonomies") or []
            if taxonomies:
                category = taxonomies[0].get("name")

            url = raw_event.get("url") or ""
            if url and url.startswith("/"):
                url = f"https://seatgeek.com{url}"

            normalized_events.append(
                {
                    "id": f"seatgeek:{source_event_id}",
                    "source": "seatgeek",
                    "source_event_id": source_event_id,
                    "name": raw_event.get("title") or "Untitled event",
                    "event_date": event_date,
                    "start_time": start_time,
                    "end_time": None,
                    "venue_name": venue.get("name") or "Unknown venue",
                    "address": ", ".join(
                        part for part in [address_line, city, state, postal_code] if part
                    ),
                    "lat": latitude,
                    "lng": longitude,
                    "organizer": None,
                    "description": None,
                    "category": category,
                    "ticket_url": url,
                    "image_url": _pick_image(raw_event),
                }
            )

        meta = payload.get("meta") or {}
        total = int(meta.get("total") or 0)
        if page * per_page >= total:
            break
        page += 1

    return [event for event in normalized_events if event["ticket_url"]]

