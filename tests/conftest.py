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
@pytest.fixture
def user_factory(db_session):
    def make_user(
        name="User",
        email=None,
        timezone_str="America/Phoenix",
    ):
        email = email or f"u+{uuid.uuid4().hex}@example.com"
        u = UserORM(name=name, email=email, timezone=timezone_str)
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u
    return make_user

@pytest.fixture
def habit_factory(db_session, user_factory):
    def make_habit(user_id=None, name="Habit"):
        if user_id is None:
            user_id = user_factory().id
        h = HabitORM(user_id=user_id, name=name)
        db_session.add(h)
        db_session.commit()
        db_session.refresh(h)
        return h
    return make_habit

@pytest.fixture
def event_factory(db_session):
    def make_event(habit_id, occurred_at=None):
        # occurred_at should be timezone-aware UTC
        occurred_at = occurred_at or datetime.now(timezone.utc)
        e = EventORM(habit_id=habit_id, occurred_at=occurred_at)
        db_session.add(e)
        db_session.commit()
        db_session.refresh(e)
        return e
    return make_event
