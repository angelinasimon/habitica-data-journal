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
