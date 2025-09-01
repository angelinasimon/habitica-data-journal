from fastapi import APIRouter
router = APIRouter()

@router.post("")
def create_habit():
    return {"ok": True, "route": "POST /habits"}

@router.get("/{habit_id}")
def get_habit(habit_id: str):
    return {"ok": True, "route": "GET /habits/{id}", "habit_id": habit_id}

@router.put("/{habit_id}")
def update_habit(habit_id: str):
    return {"ok": True, "route": "PUT /habits/{id}", "habit_id": habit_id}

@router.delete("/{habit_id}", status_code=204)
def delete_habit(habit_id: str):
    return

@router.patch("/{habit_id}/pause")
def pause_habit(habit_id: str):
    return {"ok": True, "route": "PATCH /habits/{id}/pause", "habit_id": habit_id, "status": "paused"}
