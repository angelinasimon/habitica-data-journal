from fastapi import APIRouter
router = APIRouter()

@router.post("")
def create_context():
    return {"ok": True, "route": "POST /contexts"}

@router.get("/{context_id}")
def get_context(context_id: str):
    return {"ok": True, "route": "GET /contexts/{id}", "context_id": context_id}
