from fastapi import FastAPI
from app.routers import users, habits, events, context
# ⬇️ import these from your db setup
from app.db import Base, engine

app = FastAPI(title="Habitica Data Journal (MVP)")

# ⬇️ on startup, create any missing tables in app.db
@app.on_event("startup")
def startup_create_tables():
    Base.metadata.create_all(bind=engine)

app.include_router(users.router,   prefix="/users",   tags=["users"])
app.include_router(habits.router,  prefix="/habits",  tags=["habits"])
app.include_router(events.router,  prefix="/events",  tags=["events"])
app.include_router(context.router, prefix="/contexts", tags=["contexts"])

@app.get("/ping")
def ping():
    return {"message": "pong"}
