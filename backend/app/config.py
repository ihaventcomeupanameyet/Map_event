from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    ticketmaster_api_key: str = Field(..., alias="TICKETMASTER_API_KEY")
    eventbrite_api_key: str | None = Field(None, alias="EVENTBRITE_API_KEY")
    seatgeek_client_id: str | None = Field(None, alias="SEATGEEK_CLIENT_ID")
    seatgeek_client_secret: str | None = Field(None, alias="SEATGEEK_CLIENT_SECRET")
    database_url: str = Field(..., alias="DATABASE_URL")
    backend_url: str = Field("http://localhost:8000", alias="BACKEND_URL")
    ticketmaster_base_url: str = "https://app.ticketmaster.com/discovery/v2"
    eventbrite_base_url: str = "https://www.eventbriteapi.com/v3"
    seatgeek_base_url: str = "https://api.seatgeek.com/2"
    geocoder_base_url: str = Field(
        "https://nominatim.openstreetmap.org/search",
        alias="GEOCODER_BASE_URL",
    )
    geocoder_user_agent: str = Field(
        "vancouver-event-map/0.1 (+local-dev)",
        alias="GEOCODER_USER_AGENT",
    )
    geocoder_min_interval_seconds: float = Field(
        1.0,
        alias="GEOCODER_MIN_INTERVAL_SECONDS",
    )
    events_city: str = "Vancouver"
    events_country_code: str = "CA"
    refresh_window_days: int = 30
    scheduler_hour: int = 1
    scheduler_minute: int = 0
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
