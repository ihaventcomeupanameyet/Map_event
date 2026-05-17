#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
ORGANIZERS_FILE = REPO_ROOT / "backend" / "app" / "data" / "eventbrite_vancouver_organizers.json"
DESTINATION_URL = "https://www.eventbrite.ca/d/canada--vancouver/events/"
SERVER_DATA_PATTERN = re.compile(r"window\.__SERVER_DATA__\s*=\s*(\{.*?\});", re.S)


def _load_private_token() -> str:
    token = os.getenv("EVENTBRITE_PRIVATE_TOKEN") or os.getenv("EVENTBRITE_API_KEY")
    if token:
        return token.strip()

    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("EVENTBRITE_PRIVATE_TOKEN="):
                return line.split("=", 1)[1].strip()
            if line.startswith("EVENTBRITE_API_KEY="):
                return line.split("=", 1)[1].strip()

    raise RuntimeError("Missing Eventbrite private token. Set EVENTBRITE_API_KEY or EVENTBRITE_PRIVATE_TOKEN.")


def _fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def _load_destination_server_data() -> dict[str, Any]:
    html = _fetch_text(DESTINATION_URL)
    match = SERVER_DATA_PATTERN.search(html)
    if not match:
        raise RuntimeError("Could not locate Eventbrite destination payload in Vancouver listings page.")
    return json.loads(match.group(1))


def _collect_vancouver_organizer_ids(server_data: dict[str, Any]) -> set[str]:
    organizer_ids: set[str] = set()
    for bucket in server_data.get("buckets", []):
        for key in ("events", "promoted_events"):
            for event in bucket.get(key, []):
                venue = event.get("primary_venue") or {}
                address = venue.get("address") or {}
                if address.get("city") != "Vancouver":
                    continue
                organizer_id = str(event.get("primary_organizer_id") or "").strip()
                if organizer_id:
                    organizer_ids.add(organizer_id)
    return organizer_ids


def _fetch_organizer_record(organizer_id: str, private_token: str) -> dict[str, str]:
    payload = json.loads(
        _fetch_text(
            f"https://www.eventbriteapi.com/v3/organizers/{organizer_id}/",
            headers={"Authorization": f"Bearer {private_token}"},
        )
    )
    name = str(payload.get("name") or "").strip()
    public_url = str(payload.get("url") or "").strip()
    if not name or not public_url:
        raise RuntimeError(f"Organizer {organizer_id} returned incomplete metadata.")
    return {
        "organizer_id": organizer_id,
        "name": name,
        "public_url": public_url,
    }


def _load_existing_records() -> dict[str, dict[str, str]]:
    if not ORGANIZERS_FILE.exists():
        return {}

    existing: dict[str, dict[str, str]] = {}
    for item in json.loads(ORGANIZERS_FILE.read_text(encoding="utf-8")):
        organizer_id = str(item.get("organizer_id") or "").strip()
        name = str(item.get("name") or "").strip()
        public_url = str(item.get("public_url") or "").strip()
        if organizer_id and name and public_url:
            existing[organizer_id] = {
                "organizer_id": organizer_id,
                "name": name,
                "public_url": public_url,
            }
    return existing


def main() -> None:
    private_token = _load_private_token()
    server_data = _load_destination_server_data()
    organizer_ids = _collect_vancouver_organizer_ids(server_data)
    records = _load_existing_records()

    for organizer_id in sorted(organizer_ids):
        if organizer_id not in records:
            records[organizer_id] = _fetch_organizer_record(organizer_id, private_token)

    sorted_records = sorted(
        records.values(),
        key=lambda record: (record["name"].casefold(), record["organizer_id"]),
    )
    ORGANIZERS_FILE.write_text(json.dumps(sorted_records, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(sorted_records)} Eventbrite Vancouver organizer seeds to {ORGANIZERS_FILE}")


if __name__ == "__main__":
    main()
