from fastapi import FastAPI
from app.routers import users, habits, events, context
from app.auth import router as auth_router
from app.db import Base, engine

app = FastAPI(title="Habitica Data Journal (MVP)")

@app.on_event("startup")
def startup_create_tables():
    Base.metadata.create_all(bind=engine)

# ✅ Do NOT add prefixes here if routers already have them
app.include_router(users.router)
app.include_router(habits.router)
app.include_router(events.router)
app.include_router(context.router)
app.include_router(auth_router)

@app.get("/ping")
def ping():
    return {"message": "pong"}
