from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.services.location import geocode_address, normalize_coordinates


DISCOVERY_EVENTS_PATH = "/events.json"


def _pick_image(images: list[dict]) -> str | None:
    if not images:
        return None
    best = max(images, key=lambda image: image.get("width", 0) * image.get("height", 0))
    return best.get("url")


def _pick_category(classifications: list[dict]) -> str | None:
    if not classifications:
        return None

    first = classifications[0]
    for section in ("subGenre", "genre", "segment"):
        name = first.get(section, {}).get("name")
        if name:
            return name
    return None


def _build_datetime(local_date: str, local_time: str | None, timezone_name: str | None) -> tuple[date, datetime | None]:
    event_date = date.fromisoformat(local_date)
    if not local_time:
        return event_date, None

    try:
        tz = ZoneInfo(timezone_name or "America/Vancouver")
    except Exception:
        tz = ZoneInfo("America/Vancouver")
    event_time = time.fromisoformat(local_time)
    return event_date, datetime.combine(event_date, event_time, tzinfo=tz)


async def _normalize_event(
    raw_event: dict,
    client: httpx.AsyncClient,
    settings: Settings,
    geocode_cache: dict[str, tuple[float, float] | None],
    geocode_state: dict[str, float],
) -> dict | None:
    dates = raw_event.get("dates", {}).get("start", {})
    local_date = dates.get("localDate")
    if not local_date:
        return None

    venues = raw_event.get("_embedded", {}).get("venues", [])
    if not venues:
        return None

    venue = venues[0]
    address_line = venue.get("address", {}).get("line1")
    city = venue.get("city", {}).get("name")
    state = venue.get("state", {}).get("stateCode")
    postal_code = venue.get("postalCode")
    country_name = venue.get("country", {}).get("name")
    country_code = venue.get("country", {}).get("countryCode")

    location = venue.get("location") or {}
    coordinates = normalize_coordinates(
        location.get("latitude"),
        location.get("longitude"),
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
            return None
    latitude, longitude = coordinates

    timezone_name = dates.get("timezone") or venue.get("timezone")
    event_date, start_time = _build_datetime(local_date, dates.get("localTime"), timezone_name)

    end_block = raw_event.get("dates", {}).get("end", {})
    _, end_time = _build_datetime(
        end_block.get("localDate", local_date),
        end_block.get("localTime"),
        timezone_name,
    )

    source_event_id = raw_event["id"]
    address_parts = [address_line, city, state, postal_code]
    organizer = None
    if raw_event.get("promoter"):
        organizer = raw_event["promoter"].get("name")
    elif raw_event.get("promoters"):
        organizer = raw_event["promoters"][0].get("name")

    return {
        "id": f"ticketmaster:{source_event_id}",
        "source": "ticketmaster",
        "source_event_id": source_event_id,
        "name": raw_event.get("name", "Untitled event"),
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "venue_name": venue.get("name", "Unknown venue"),
        "address": ", ".join(part for part in address_parts if part),
        "lat": latitude,
        "lng": longitude,
        "organizer": organizer,
        "description": raw_event.get("info") or raw_event.get("pleaseNote"),
        "category": _pick_category(raw_event.get("classifications", [])),
        "ticket_url": raw_event.get("url", ""),
        "image_url": _pick_image(raw_event.get("images", [])),
    }


async def fetch_ticketmaster_events(
    client: httpx.AsyncClient,
    settings: Settings,
) -> list[dict]:
    now = datetime.now(tz=ZoneInfo("UTC"))
    end = now + timedelta(days=settings.refresh_window_days)

    params = {
        "apikey": settings.ticketmaster_api_key,
        "city": settings.events_city,
        "countryCode": settings.events_country_code,
        "startDateTime": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "endDateTime": end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "size": 200,
        "sort": "date,asc",
    }

    normalized_events: list[dict] = []
    geocode_cache: dict[str, tuple[float, float] | None] = {}
    geocode_state = {"last_request_at": 0.0}
    page = 0

    while True:
        response = await client.get(
            f"{settings.ticketmaster_base_url}{DISCOVERY_EVENTS_PATH}",
            params={**params, "page": page},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()

        for raw_event in payload.get("_embedded", {}).get("events", []):
            normalized = await _normalize_event(
                raw_event,
                client,
                settings,
                geocode_cache,
                geocode_state,
            )
            if normalized and normalized["ticket_url"]:
                normalized_events.append(normalized)

        page_info = payload.get("page", {})
        total_pages = page_info.get("totalPages", 0)
        if page + 1 >= total_pages:
            break
        page += 1

    return normalized_events

