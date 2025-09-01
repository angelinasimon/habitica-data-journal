from fastapi import APIRouter
router = APIRouter()

@router.post("")
def create_event():
    return {"ok": True, "route": "POST /events"}

@router.get("/{event_id}")
def get_event(event_id: str):
    return {"ok": True, "route": "GET /events/{id}", "event_id": event_id}
