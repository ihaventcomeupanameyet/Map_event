from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
from time import monotonic
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings


DISCOVERY_EVENTS_PATH = "/events.json"
GEOCODER_RESULT_LIMIT = 1


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


def _normalize_coordinates(
    latitude: str | float | None,
    longitude: str | float | None,
    country_code: str | None,
) -> tuple[float, float] | None:
    if latitude is None or longitude is None:
        return None

    lat = float(latitude)
    lng = float(longitude)

    # A few venues come back as (0, 0), which places them off west Africa.
    # Treat that as missing location data instead of caching a fake point.
    if lat == 0.0 and lng == 0.0:
        return None

    # Ticketmaster occasionally returns western hemisphere venues with a missing
    # minus sign on longitude. Correct the obvious CA/US case before caching.
    if country_code in {"CA", "US"} and lng > 0:
        lng = -lng

    return lat, lng


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


def _is_vancouver_area_coordinate(lat: float, lng: float) -> bool:
    return 48.8 <= lat <= 49.6 and -123.4 <= lng <= -122.0


def _build_geocode_cache_key(venue: dict) -> str | None:
    address = venue.get("address", {}).get("line1")
    city = venue.get("city", {}).get("name")
    state = venue.get("state", {}).get("stateCode") or venue.get("state", {}).get("name")
    postal_code = venue.get("postalCode")
    country = venue.get("country", {}).get("countryCode") or venue.get("country", {}).get("name")

    parts = [address, city, state, postal_code, country]
    if not any(parts):
        return None

    return "|".join(part.strip() for part in parts if part)


async def _geocode_venue_coordinates(
    client: httpx.AsyncClient,
    settings: Settings,
    venue: dict,
    geocode_cache: dict[str, tuple[float, float] | None],
    geocode_state: dict[str, float],
) -> tuple[float, float] | None:
    cache_key = _build_geocode_cache_key(venue)
    if not cache_key:
        return None

    if cache_key in geocode_cache:
        return geocode_cache[cache_key]

    elapsed = monotonic() - geocode_state["last_request_at"]
    min_interval = settings.geocoder_min_interval_seconds
    if elapsed < min_interval:
        await asyncio.sleep(min_interval - elapsed)

    params = {
        "street": venue.get("address", {}).get("line1"),
        "city": venue.get("city", {}).get("name"),
        "state": venue.get("state", {}).get("name") or venue.get("state", {}).get("stateCode"),
        "postalcode": venue.get("postalCode"),
        "country": venue.get("country", {}).get("name"),
        "countrycodes": (venue.get("country", {}).get("countryCode") or "").lower() or None,
        "format": "jsonv2",
        "limit": GEOCODER_RESULT_LIMIT,
    }
    params = {key: value for key, value in params.items() if value}

    response = await client.get(
        settings.geocoder_base_url,
        params=params,
        headers={"User-Agent": settings.geocoder_user_agent},
        timeout=30.0,
    )
    geocode_state["last_request_at"] = monotonic()
    response.raise_for_status()

    payload = response.json()
    if not payload:
        geocode_cache[cache_key] = None
        return None

    try:
        lat = float(payload[0]["lat"])
        lng = float(payload[0]["lon"])
    except (KeyError, TypeError, ValueError):
        geocode_cache[cache_key] = None
        return None

    if not _is_vancouver_area_coordinate(lat, lng):
        geocode_cache[cache_key] = None
        return None

    geocode_cache[cache_key] = (lat, lng)
    return geocode_cache[cache_key]


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
    location = venue.get("location") or {}
    coordinates = _normalize_coordinates(
        location.get("latitude"),
        location.get("longitude"),
        venue.get("country", {}).get("countryCode"),
    )
    if coordinates is None:
        coordinates = await _geocode_venue_coordinates(
            client,
            settings,
            venue,
            geocode_cache,
            geocode_state,
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
    address_parts = [
        venue.get("address", {}).get("line1"),
        venue.get("city", {}).get("name"),
        venue.get("state", {}).get("stateCode"),
        venue.get("postalCode"),
    ]
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
