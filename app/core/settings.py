from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict  # <-- v2 import

class Settings(BaseSettings):
    # General
    TESTING: bool = False
    TIMEZONE: str = "UTC"

    # Scheduling
    REMINDER_CRON: Optional[str] = None   # e.g., "0 9 * * *"
    REMINDER_INTERVAL_MINUTES: int = 15

    # Optional kill switch
    DISABLE_SCHEDULER: bool = False

    # Analytics / Feature Engineering
    # Define "hour buckets" for habits. Format: name=startHour-endHour, comma-separated.
    # Wrap-around supported (e.g., "night=22-5").
    TIME_BUCKETS: str = "morning=5-11,afternoon=11-17,evening=17-22,night=22-5"

    # Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
