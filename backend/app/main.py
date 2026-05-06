import logging
from contextlib import asynccontextmanager
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine, get_session
from app.models import Event
from app.schemas import EventResponse, RefreshResponse
from app.services.refresh import is_events_table_empty, refresh_events


logger = logging.getLogger(__name__)
settings = get_settings()


async def run_refresh_job() -> None:
    async with AsyncSessionLocal() as session:
        try:
            stats = await refresh_events(session, settings=settings)
            logger.info(
                "Event refresh completed. fetched=%s upserted=%s removed_expired=%s",
                stats.fetched,
                stats.upserted,
                stats.removed_expired,
            )
        except Exception:
            logger.exception("Nightly refresh job failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_refresh_job,
        CronTrigger(hour=settings.scheduler_hour, minute=settings.scheduler_minute),
        id="nightly-event-refresh",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()

    async with AsyncSessionLocal() as session:
        if await is_events_table_empty(session):
            logger.info("Events table is empty. Running one-time startup refresh.")
            await refresh_events(session, settings=settings)

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()


app = FastAPI(title="Vancouver Event Discovery API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events", response_model=list[EventResponse])
async def get_events(
    event_date: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
) -> list[Event]:
    result = await session.scalars(
        select(Event)
        .where(Event.event_date == event_date)
        .order_by(Event.start_time.asc().nulls_last(), Event.name.asc())
    )
    return list(result.all())


@app.post("/jobs/refresh-events", response_model=RefreshResponse)
async def refresh_events_endpoint(
    session: AsyncSession = Depends(get_session),
) -> RefreshResponse:
    stats = await refresh_events(session, settings=settings)
    return RefreshResponse(
        fetched=stats.fetched,
        upserted=stats.upserted,
        removedExpired=stats.removed_expired,
    )

