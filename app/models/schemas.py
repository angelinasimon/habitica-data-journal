from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID

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
