from fastapi import FastAPI
from app.routers import users, habits, events, context

app = FastAPI(title="Habitica Data Journal (MVP)")

app.include_router(users.router,   prefix="/users",   tags=["users"])
app.include_router(habits.router,  prefix="/habits",  tags=["habits"])
app.include_router(events.router,  prefix="/events",  tags=["events"])
app.include_router(context.router, prefix="/contexts", tags=["context"])

@app.get("/ping")
def ping():
    return {"message": "pong"}