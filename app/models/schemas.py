# app/models/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator, AliasChoices
from typing import Optional, Any, Dict
from datetime import datetime, date, timezone
from uuid import UUID
from enum import Enum
from zoneinfo import ZoneInfo

# ---------- Enums ----------
class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class HabitStatus(str, Enum):
    active = "active"
    paused = "paused"
    archived = "archived"

class ContextKind(str, Enum):
    travel = "travel"
    exam = "exam"
    illness = "illness"
    custom = "custom"

# ---------- User ----------
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

# ---------- Habit ----------
class HabitCreate(BaseModel):
    user_id: UUID | None = None
    name: str
    difficulty: Difficulty = Difficulty.medium
    status: HabitStatus = HabitStatus.active
    timezone: Optional[str] = None
    start_date: Optional[date] = None

class HabitRead(BaseModel):
    # v2 style only; remove any class Config elsewhere
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: int
    user_id: UUID            # <-- NOTE the colon, not equals
    name: str
    difficulty: Difficulty
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

# ---------- Streak ----------
class Streak(BaseModel):
    current: int
    max: int
    last_completed: Optional[date]

# ---------- Events ----------
class EventCreate(BaseModel):
    # Accept either 'occurred_at_utc' (tests/reminders) OR 'occurred_at' (your other tests)
    occurred_at: datetime = Field(validation_alias=AliasChoices("occurred_at_utc", "occurred_at"))
    habit_id: int

    @field_validator("occurred_at")
    @classmethod
    def default_to_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: int
    habit_id: int
    occurred_at: datetime = Field(alias="occurred_at_utc")
    created_at: datetime

# ---------- Context ----------
class ContextCreate(BaseModel):
    kind: str
    start: datetime
    end: Optional[datetime] = None
    data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("start", "end")
    @classmethod
    def ensure_tz(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        return v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)

class ContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: int
    kind: ContextKind
    start: datetime = Field(alias="start_utc")
    end: Optional[datetime] = Field(alias="end_utc")
    data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

# ---------- Reminders ----------
class ReminderDue(BaseModel):
    habit_id: int
    habit_name: str
