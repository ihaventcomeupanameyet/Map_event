from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventResponse(BaseModel):
    id: str
    source: str
    source_event_id: str = Field(alias="sourceEventId")
    name: str
    start_time: datetime | None = Field(alias="startTime")
    end_time: datetime | None = Field(default=None, alias="endTime")
    venue_name: str = Field(alias="venueName")
    address: str | None = None
    lat: float
    lng: float
    organizer: str | None = None
    description: str | None = None
    category: str | None = None
    ticket_url: str = Field(alias="ticketUrl")
    image_url: str | None = Field(default=None, alias="imageUrl")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RefreshResponse(BaseModel):
    fetched: int
    upserted: int
    removed_expired: int = Field(alias="removedExpired")
    removed_stale: int = Field(alias="removedStale")

    model_config = ConfigDict(populate_by_name=True)
