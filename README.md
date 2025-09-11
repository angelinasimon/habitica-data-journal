A work-in-progress habit tracker that uses FastAPI and Python.  
The goal is to log habits, analyze streaks and trends, and eventually add smart features like pausing habits during travel and making predictions.

## Project Journal

### Day 1 — August 31, 2025
- Set up project folder and virtual environment.
- Installed FastAPI, Uvicorn, pytest, and python-dotenv.
- Saved dependencies in requirements.txt.
- Added first endpoint `/ping` → returns `{"message":"pong"}`.
- Tested in browser, worked fine.

### Day 2 — September 1, 2025
- Mapped out core entities (`users`, `habits`, `events`, `contexts`) and their relationships.
- Drafted CRUD + special endpoints (e.g., `PATCH /habits/{id}/pause`).
- Split routes into `users.py`, `habits.py`, `events.py`, `contexts.py` and wired them into `main.py`.
- Verified all endpoints respond with stub JSON via Swagger UI (`/docs`) — skeleton API is live.

### Day 3 — September 2, 2025

- Activated virtual environment and installed dependencies (`sqlalchemy`, `pydantic[email]`, `pytest`, `requests`)
- Added `app/models/schemas.py` with Pydantic models (`UserCreate`, `User`)
- Built `app/db.py` with:
  - SQLite engine (`app.db`)
  - Session setup (`SessionLocal`, `get_db`)
  - ORM models (User + placeholders for Habit, Context, Event)
- Updated `app/main.py` to create tables on startup
- Implemented database-backed user endpoints in `app/routers/users.py`:
  - **POST /users** → create user (409 on duplicate email)
  - **GET /users/{id}** → fetch user (404 if not found)
  - **PUT /users/{id}** → update user (handles email conflicts)
  - **DELETE /users/{id}** → delete user
- Verified SQLite persistence by running server (`uvicorn`) and checking `app.db`
- Tested endpoints with Swagger UI:
  - Created user, retrieved by id, confirmed duplicate email returns 409
- Added `tests/test_app.py` with:
  - `test_ping` → GET /ping returns 200 + "pong"
  - `test_create_user` → POST /users returns 201 with UUID id
- Ran pytest → all tests passed
- Locked dependencies with `pip freeze > requirements.txt`
- Updated README to reflect:
  - SQLite persistence
  - Real User endpoints
  - Two passing tests

### Day 4 — September 3–4, 2025  
- **Habit model & CRUD**  
  - Implemented `HabitORM` with difficulty/status enums and relationships to events.  
  - Added `app/crud/habits.py` with full create, read, update, pause/resume logic and soft name-conflict handling.  
  - Built `POST /habits`, `GET /habits/{id}`, and `PATCH /habits/{id}` (pause/resume) endpoints with validation.  

- **Context model & basic API**  
  - Implemented `ContextORM` (travel/exam windows).  
  - Added `POST /contexts` to create a window and `GET /contexts` to list all or filter by `active_only`.  
  - Wrote tests to verify overlapping windows, date-range validation, and “active only” filtering.

---

### Day 5 — September 5–6, 2025  
- **Event tracking**  
  - Added `EventORM` and `app/crud/events.py` to log habit completions with UTC storage and local-day idempotence.  
  - Built `POST /events` to record a habit event and `GET /habits/{id}/events?start=&end=` to list by date range.  
  - Guarded against duplicate same-day events per user’s local time zone.  

- **Service: streak computation**  
  - Implemented `app/services/streaks.py::compute_streaks` to calculate `{current, max, last_completed}` for each habit.  
  - Added `GET /habits/{id}/streak` endpoint and validated edge cases:
    - Multiple events in one day collapse to one.
    - Time-zone midnight boundaries.
    - “As-of” historical queries.

---

### Day 6 — September 7–10, 2025  
- **Robust testing & bug fixes**  
  - Wrote and refined full test suite:
    - User → habit → event flow with correct streak math.
    - Paused habits reject new events.
    - Context windows behave correctly when filtering.
    - Integration flow combining users, habits, events, and contexts.
  - Iterated through multiple fixes:
    - Removed DB-specific SQL functions for SQLite compatibility.
    - Adjusted event creation to enforce local-day uniqueness entirely in Python.
    - Synced Pydantic `Streak` schema with API responses.
  - Achieved **100% passing tests** across `tests/test_app.py`, `test_habits_api.py`, `test_events_api.py`, `test_contexts_api.py`, and `test_integration_flow.py`.
"
