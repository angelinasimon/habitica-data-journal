# tests/conftest.py
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

# Import your app + DB stuff
from app.main import app
from app.db import (
    Base, get_db,
    UserORM, HabitORM, EventORM,
    Difficulty, HabitStatus,  # <-- enums from your models/schemas integration
)

# --- Shared in-memory SQLite for the whole test run ---
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# --- Create/drop schema once per test session ---
@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

# --- Per-test DB session ---
@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

# --- FastAPI client using the test DB via dependency override ---
@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# --- Simple factories to insert rows quickly in tests ---

@pytest.fixture
def user_factory(db_session):
    def make_user(
        name: str = "User",
        email: str | None = None,
        timezone_str: str | None = "America/Phoenix",
        **kwargs,  # allow calls like timezone="America/Phoenix"
    ):
        if "timezone" in kwargs and kwargs["timezone"] is not None:
            timezone_str = kwargs["timezone"]

        email = email or f"u+{uuid.uuid4().hex}@example.com"
        u = UserORM(name=name, email=email, timezone=timezone_str)
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u
    return make_user

def _to_enum(val, enum_cls):
    if isinstance(val, enum_cls):
        return val
    return enum_cls(val)

@pytest.fixture
def habit_factory(db_session, user_factory):
    def make_habit(
        user_id: str | None = None,
        name: str = "Habit",
        difficulty: Difficulty | str = Difficulty.medium,
        status: HabitStatus | str = HabitStatus.active,
    ):
        if user_id is None:
            user_id = user_factory().id

        # Coerce strings to your enum types
        difficulty = _to_enum(difficulty, Difficulty)
        status = _to_enum(status, HabitStatus)

        h = HabitORM(
            user_id=user_id,
            name=name,
            difficulty=difficulty,
            name_canonical=name.strip().lower(),
            status=status,
        )
        db_session.add(h)
        db_session.commit()
        db_session.refresh(h)
        return h
    return make_habit

@pytest.fixture
def event_factory(db_session):
    def make_event(*, habit_id: int, occurred_at_utc: datetime | None = None, occurred_at: datetime | None = None):
        # prefer explicit UTC param; fall back to "occurred_at"
        ts = occurred_at_utc or occurred_at
        if ts is None:
            raise AssertionError("Provide occurred_at_utc (preferred) or occurred_at")

        # ensure aware UTC datetime
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        e = EventORM(habit_id=habit_id, occurred_at_utc=ts)
        db_session.add(e)
        db_session.commit()
        db_session.refresh(e)
        return e
    return make_event
