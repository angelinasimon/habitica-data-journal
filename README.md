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


