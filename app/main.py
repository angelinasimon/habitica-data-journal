from fastapi import FastAPI
from app.routers import users, habits, events, context, admin
from app.auth import router as auth_router
from app.db import Base, engine
from app.services.scheduler import start_scheduler, shutdown_scheduler
import logging


logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Habitica Data Journal (MVP)")

@app.on_event("startup")
def startup_create_tables():
    Base.metadata.create_all(bind=engine)

# ✅ Do NOT add prefixes here if routers already have them

app.include_router(admin.router)
app.include_router(users.router)
app.include_router(habits.router)
app.include_router(events.router)
app.include_router(context.router)
app.include_router(auth_router)

@app.on_event("startup")
def _on_startup():
    start_scheduler(app)

@app.on_event("shutdown")
def _on_shutdown():
    shutdown_scheduler(app)

@app.get("/ping")
def ping():
    return {"message": "pong"}
