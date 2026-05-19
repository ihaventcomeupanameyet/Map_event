from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Event
from app.services.eventbrite import fetch_eventbrite_events
from app.services.seatgeek import fetch_seatgeek_events
from app.services.ticketmaster import fetch_ticketmaster_events


logger = logging.getLogger(__name__)


@dataclass
class RefreshStats:
    fetched: int
    upserted: int
    removed_expired: int
    removed_stale: int


async def is_events_table_empty(session: AsyncSession) -> bool:
    result = await session.scalar(select(func.count()).select_from(Event))
    return bool(result == 0)


async def refresh_events(
    session: AsyncSession,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> RefreshStats:
    settings = settings or get_settings()
    owns_client = client is None
    now = datetime.now(timezone.utc)

    if owns_client:
        client = httpx.AsyncClient()

    try:
        normalized_events = []
        successful_providers: list[str] = []
        providers = [
            ("ticketmaster", fetch_ticketmaster_events),
            ("eventbrite", fetch_eventbrite_events),
            ("seatgeek", fetch_seatgeek_events),
        ]
        for provider_name, fetcher in providers:
            try:
                provider_events = await fetcher(client, settings)
                normalized_events.extend(provider_events)
                successful_providers.append(provider_name)
                logger.info(
                    "Provider refresh completed. provider=%s fetched=%s",
                    provider_name,
                    len(provider_events),
                )
            except Exception:
                logger.exception("Provider refresh failed: %s", provider_name)
    finally:
        if owns_client and client is not None:
            await client.aclose()

    upserted = 0
    if normalized_events:
        records = [{**event, "last_seen_at": now} for event in normalized_events]
        insert_stmt = pg_insert(Event).values(records)
        update_columns = {
            column.name: getattr(insert_stmt.excluded, column.name)
            for column in Event.__table__.columns
            if column.name != "id"
        }
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[Event.id],
            set_=update_columns,
        )
        result = await session.execute(upsert_stmt)
        upserted = result.rowcount or len(records)

    expired_condition = or_(
        and_(Event.end_time.is_not(None), Event.end_time < now),
        and_(Event.end_time.is_(None), Event.start_time.is_not(None), Event.start_time < now),
        and_(Event.end_time.is_(None), Event.start_time.is_(None), Event.event_date < now.date()),
    )

    invalid_location_condition = and_(Event.lat == 0.0, Event.lng == 0.0)

    delete_stmt = delete(Event).where(or_(expired_condition, invalid_location_condition))
    delete_result = await session.execute(delete_stmt)

    removed_stale = 0
    if successful_providers:
        stale_stmt = delete(Event).where(
            and_(
                Event.source.in_(successful_providers),
                Event.last_seen_at < now,
            )
        )
        stale_result = await session.execute(stale_stmt)
        removed_stale = stale_result.rowcount or 0

    await session.commit()

    return RefreshStats(
        fetched=len(normalized_events),
        upserted=upserted,
        removed_expired=delete_result.rowcount or 0,
        removed_stale=removed_stale,
    )
