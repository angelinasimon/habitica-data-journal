# tests/conftest.py
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone, date

# Import your app + DB stuff
from app.main import app
from app.db import Base, get_db, UserORM, HabitORM, EventORM  # make sure these exist

# --- Build a shared in-memory SQLite engine for the whole test run ---
# StaticPool + "sqlite://" (no file) keeps one shared in-memory DB across threads.
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

# --- Per-test DB session (rolled back/closed after each test) ---
@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        # in case the test forgot to commit
        db.rollback()
        db.close()

# --- FastAPI client that uses the test DB via dependency override ---
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
# tests/conftest.py

@pytest.fixture
def user_factory(db_session):
    def make_user(
        name="User",
        email=None,
        timezone_str="America/Phoenix",
        **kwargs,                    # accept extra aliases
    ):
        # allow test calls like timezone="America/Phoenix"
        if "timezone" in kwargs and kwargs["timezone"] is not None:
            timezone_str = kwargs["timezone"]

        email = email or f"u+{uuid.uuid4().hex}@example.com"
        u = UserORM(name=name, email=email, timezone=timezone_str)
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u
    return make_user

@pytest.fixture
def habit_factory(db_session, user_factory):
    def make_habit(
        user_id=None,
        name="Habit",
        start_date=None,
        timezone_str="America/Phoenix",  # include if your model has a NOT NULL timezone
        status="active",                 # include if NOT NULL with no server_default
        difficulty="normal",             # include if NOT NULL with no server_default
    ):
        if user_id is None:
            user_id = user_factory().id
        if start_date is None:
            start_date = date.today()  # or date in the user’s tz if you prefer

        # Adjust kwargs to exactly match your HabitORM signature.
        h = HabitORM(
            user_id=user_id,
            name=name,
            start_date=start_date,
            # Only include these if your model defines them and they’re NOT NULL:
            # timezone=timezone_str,
            # status=status,
            # difficulty=difficulty,
        )
        db_session.add(h)
        db_session.commit()
        db_session.refresh(h)
        return h
    return make_habit

@pytest.fixture
def event_factory(db_session):
    def make_event(*, habit_id, occurred_at=None, occurred_at_utc=None):
        # prefer explicit UTC param; fall back to "occurred_at"
        ts = occurred_at_utc or occurred_at
        if ts is None:
            raise AssertionError("Provide occurred_at_utc (preferred) or occurred_at")

        # ensure aware UTC datetime
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        e = EventORM(habit_id=habit_id)
        if hasattr(EventORM, "occurred_at_utc"):
            e.occurred_at_utc = ts
        elif hasattr(EventORM, "occurred_at"):
            e.occurred_at = ts
        else:
            raise AssertionError("EventORM needs a datetime field named occurred_at_utc or occurred_at")

        db_session.add(e)
        db_session.commit()
        db_session.refresh(e)
        return e
    return make_event