from __future__ import annotations
from pydantic import BaseModel, EmailStr, field_validator
from pydantic import ConfigDict  # pydantic v2 style config
from typing import Optional, Any, Dict
from datetime import datetime, date, timezone
from uuid import UUID
from enum import Enum
from zoneinfo import ZoneInfo



class Streak(BaseModel):
    current: int
    max: int
    last_completed: date | None

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    timezone: Optional[str] = "America/Phoenix"

class User(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    timezone: Optional[str] = "America/Phoenix"
    created_at: datetime
    updated_at: datetime

# app/models/enums.py
from enum import Enum  # Python's Enum

class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class HabitStatus(str, Enum):
    active = "active"
    paused = "paused"
    archived = "archived"

# You can keep Context kind as free text for now; add an Enum later if helpful.

class HabitCreate(BaseModel):
    name: str
    difficulty: Difficulty = Difficulty.medium
    timezone: str
    start_date: date | None = None

class HabitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2 "orm_mode"
    id: int
    name: str
    difficulty: Difficulty
    timezone: str
    start_date: date
    status: HabitStatus


class HabitPatch(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    timezone: Optional[str] = None
    status: Optional[HabitStatus] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError("Invalid IANA timezone string")
        return v

    def as_update_dict(self) -> dict:
        # Use this in your CRUD layer to build partial updates safely.
        return self.model_dump(exclude_unset=True, exclude_none=True)

# ---------- Event Schemas ----------
class EventCreate(BaseModel):
    habit_id: UUID
    occurred_at: datetime  # client sends ISO 8601 (e.g., "2025-09-03T15:00:00-07:00")

    @field_validator("occurred_at")
    @classmethod
    def default_to_utc(cls, v: datetime) -> datetime:
        # Store everything in UTC for consistency
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    habit_id: UUID
    occurred_at: datetime  # UTC
    created_at: datetime

# ---------- Context Schemas ----------
class ContextCreate(BaseModel):
    kind: str
    start: datetime
    end: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("start", "end")
    @classmethod
    def ensure_tz(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        # If naive, assume UTC; if aware, leave as-is (you can also normalize to UTC here).
        return v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)

class ContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    start: datetime
    end: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime