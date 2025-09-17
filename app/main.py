from fastapi import FastAPI
from app.routers import users, habits, events, context, admin, analytics
from app.auth import router as auth_router
from contextlib import asynccontextmanager
from app.db import Base, engine
from app.services.scheduler import start_scheduler, shutdown_scheduler
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # start once
    start_scheduler(app)
    try:
        yield
    finally:
        # clean stop
        shutdown_scheduler(app)

# ✅ add lifespan here; keep your title
app = FastAPI(title="Habitica Data Journal (MVP)", lifespan=lifespan)

# Create tables on startup (this can stay as an event alongside lifespan)
@app.on_event("startup")
def startup_create_tables():
    Base.metadata.create_all(bind=engine)

# Routers
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(habits.router)
app.include_router(events.router)
app.include_router(context.router)
app.include_router(auth_router)
app.include_router(analytics.router)

@app.get("/ping")
def ping():
    return {"message": "pong"}