from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.services.location import (
    geocode_address,
    is_vancouver_area_coordinate,
    normalize_coordinates,
)


ORGANIZERS_FILE = Path(__file__).resolve().parents[1] / "data" / "eventbrite_vancouver_organizers.json"
EVENTBRITE_ORGANIZER_EVENTS_PATH = "/organizers/{organizer_id}/events/"
EVENTBRITE_ME_PATH = "/users/me/"
METRO_VANCOUVER_REGION_NAMES = {"bc", "british columbia"}
logger = logging.getLogger(__name__)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _event_date_from_start(start_time: datetime | None) -> date | None:
    if start_time is None:
        return None
    return start_time.astimezone(ZoneInfo("America/Vancouver")).date()


def _pick_eventbrite_image(raw_event: dict) -> str | None:
    logo = raw_event.get("logo") or {}
    original = logo.get("original") or {}
    return original.get("url") or logo.get("url")


def _format_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:200]

    details = [payload.get("error"), payload.get("error_description")]
    return " - ".join(part for part in details if part)


def _normalize_country_code(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None

    upper = normalized.upper()
    if len(upper) == 2:
        return upper

    lowered = normalized.casefold()
    if lowered == "canada":
        return "CA"
    if lowered in {"united states", "united states of america", "usa"}:
        return "US"
    return None


def _is_allowed_region(value: str | None) -> bool:
    if not isinstance(value, str):
        return True

    normalized = value.strip().casefold().replace(".", "")
    if not normalized:
        return True

    return normalized in METRO_VANCOUVER_REGION_NAMES


def _load_seed_organizers() -> list[dict[str, str]]:
    payload = json.loads(ORGANIZERS_FILE.read_text(encoding="utf-8"))
    organizers: list[dict[str, str]] = []
    for item in payload:
        organizer_id = str(item.get("organizer_id", "")).strip()
        name = str(item.get("name", "")).strip()
        public_url = str(item.get("public_url", "")).strip()
        if not organizer_id or not name:
            continue
        organizers.append(
            {
                "organizer_id": organizer_id,
                "name": name,
                "public_url": public_url,
            }
        )
    return organizers


async def _validate_eventbrite_token(
    client: httpx.AsyncClient,
    settings: Settings,
    headers: dict[str, str],
) -> None:
    response = await client.get(
        f"{settings.eventbrite_base_url}{EVENTBRITE_ME_PATH}",
        headers=headers,
        timeout=30.0,
    )
    if response.status_code == 401:
        raise RuntimeError(
            "Eventbrite authentication failed. EVENTBRITE_API_KEY must be an Eventbrite private token, and the configured value was rejected by /users/me/."
        )
    response.raise_for_status()


async def fetch_eventbrite_events(
    client: httpx.AsyncClient,
    settings: Settings,
) -> list[dict]:
    if not settings.eventbrite_api_key:
        return []

    now = datetime.now(tz=ZoneInfo("UTC"))
    end = now + timedelta(days=settings.refresh_window_days)
    headers = {"Authorization": f"Bearer {settings.eventbrite_api_key}"}
    await _validate_eventbrite_token(client, settings, headers)
    seed_organizers = _load_seed_organizers()
    logger.info("Eventbrite organizer seed loaded. organizers=%s", len(seed_organizers))

    normalized_events: list[dict] = []
    geocode_cache: dict[str, tuple[float, float] | None] = {}
    geocode_state = {"last_request_at": 0.0}
    for organizer in seed_organizers:
        organizer_id = organizer["organizer_id"]
        page = 1
        organizer_event_count = 0
        organizer_skipped_location_count = 0

        while True:
            params = {
                "status": "live",
                "expand": "venue,organizer,category,subcategory",
                "page": page,
            }
            response = await client.get(
                f"{settings.eventbrite_base_url}{EVENTBRITE_ORGANIZER_EVENTS_PATH.format(organizer_id=organizer_id)}",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            if response.status_code == 404:
                detail = _format_error_detail(response)
                logger.warning(
                    "Eventbrite organizer fetch skipped. organizer_id=%s detail=%s",
                    organizer_id,
                    detail,
                )
                break
            response.raise_for_status()
            payload = response.json()

            for raw_event in payload.get("events", []):
                venue = raw_event.get("venue") or {}
                if not venue or raw_event.get("online_event"):
                    continue

                source_event_id = str(raw_event["id"])
                address = venue.get("address") or {}
                address_line = address.get("address_1")
                city = address.get("city")
                state = address.get("region")
                postal_code = address.get("postal_code")
                raw_country = address.get("country")
                country_code = _normalize_country_code(raw_country)
                country_name = "Canada" if country_code == "CA" else raw_country

                if country_code and country_code != settings.events_country_code:
                    organizer_skipped_location_count += 1
                    continue
                if not _is_allowed_region(state):
                    organizer_skipped_location_count += 1
                    continue

                coordinates = normalize_coordinates(
                    venue.get("latitude"),
                    venue.get("longitude"),
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
                if not is_vancouver_area_coordinate(latitude, longitude):
                    organizer_skipped_location_count += 1
                    continue

                start_time = _parse_iso_datetime((raw_event.get("start") or {}).get("utc"))
                if start_time is None or start_time > end:
                    continue
                end_time = _parse_iso_datetime((raw_event.get("end") or {}).get("utc"))
                event_date = _event_date_from_start(start_time)
                if event_date is None:
                    continue

                category = None
                if raw_event.get("subcategory"):
                    category = raw_event["subcategory"].get("name")
                elif raw_event.get("category"):
                    category = raw_event["category"].get("name")

                organizer_info = raw_event.get("organizer") or {}
                ticket_url = raw_event.get("vanity_url") or raw_event.get("url") or ""
                if not ticket_url:
                    continue

                normalized_events.append(
                    {
                        "id": f"eventbrite:{source_event_id}",
                        "source": "eventbrite",
                        "source_event_id": source_event_id,
                        "name": raw_event.get("name", {}).get("text") or "Untitled event",
                        "event_date": event_date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "venue_name": venue.get("name") or "Unknown venue",
                        "address": ", ".join(
                            part for part in [address_line, city, state, postal_code] if part
                        ),
                        "lat": latitude,
                        "lng": longitude,
                        "organizer": organizer_info.get("name") or organizer["name"],
                        "description": (raw_event.get("description") or {}).get("text"),
                        "category": category,
                        "ticket_url": ticket_url,
                        "image_url": _pick_eventbrite_image(raw_event),
                    }
                )
                organizer_event_count += 1

            pagination = payload.get("pagination") or {}
            if not pagination.get("has_more_items"):
                break
            page += 1

        logger.info(
            "Eventbrite organizer fetch completed. organizer_id=%s organizer=%s fetched=%s skipped_outside_vancouver=%s",
            organizer_id,
            organizer["name"],
            organizer_event_count,
            organizer_skipped_location_count,
        )

    deduplicated_events = list(
        {event["source_event_id"]: event for event in normalized_events}.values()
    )
    logger.info("Eventbrite fetch completed. fetched=%s", len(deduplicated_events))
    return deduplicated_events
