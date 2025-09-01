from fastapi import APIRouter
router = APIRouter()

@router.post("")
def create_user():
    return {"ok": True, "route": "POST /users"}

@router.get("/{user_id}")
def get_user(user_id: str):
    return {"ok": True, "route": "GET /users/{id}", "user_id": user_id}

@router.put("/{user_id}")
def update_user(user_id: str):
    return {"ok": True, "route": "PUT /users/{id}", "user_id": user_id}

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str):
    return
