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

    # Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
