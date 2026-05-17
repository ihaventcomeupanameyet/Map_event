from __future__ import annotations

import asyncio
from time import monotonic

import httpx

from app.config import Settings


GEOCODER_RESULT_LIMIT = 1


def is_vancouver_area_coordinate(lat: float, lng: float) -> bool:
    return 48.8 <= lat <= 49.6 and -123.4 <= lng <= -122.0


def normalize_coordinates(
    latitude: str | float | None,
    longitude: str | float | None,
    country_code: str | None,
) -> tuple[float, float] | None:
    if latitude is None or longitude is None:
        return None

    lat = float(latitude)
    lng = float(longitude)

    # Some upstream records use (0, 0) as a placeholder, which maps off west Africa.
    if lat == 0.0 and lng == 0.0:
        return None

    # Western hemisphere coordinates for CA/US venues should be negative longitude.
    if country_code in {"CA", "US"} and lng > 0:
        lng = -lng

    if country_code == "CA" and not is_vancouver_area_coordinate(lat, lng):
        return None

    return lat, lng


def build_geocode_cache_key(
    address_line: str | None,
    city: str | None,
    state: str | None,
    postal_code: str | None,
    country: str | None,
) -> str | None:
    parts = [address_line, city, state, postal_code, country]
    if not any(parts):
        return None

    return "|".join(part.strip() for part in parts if part)


async def geocode_address(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    address_line: str | None,
    city: str | None,
    state: str | None,
    postal_code: str | None,
    country: str | None,
    country_code: str | None,
    geocode_cache: dict[str, tuple[float, float] | None],
    geocode_state: dict[str, float],
) -> tuple[float, float] | None:
    cache_key = build_geocode_cache_key(address_line, city, state, postal_code, country)
    if not cache_key:
        return None

    if cache_key in geocode_cache:
        return geocode_cache[cache_key]

    elapsed = monotonic() - geocode_state["last_request_at"]
    min_interval = settings.geocoder_min_interval_seconds
    if elapsed < min_interval:
        await asyncio.sleep(min_interval - elapsed)

    params = {
        "street": address_line,
        "city": city,
        "state": state,
        "postalcode": postal_code,
        "country": country,
        "countrycodes": (country_code or "").lower() or None,
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

    if country_code == "CA" and not is_vancouver_area_coordinate(lat, lng):
        geocode_cache[cache_key] = None
        return None

    geocode_cache[cache_key] = (lat, lng)
    return geocode_cache[cache_key]

