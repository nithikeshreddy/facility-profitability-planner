from fastapi import APIRouter

from app.schemas import ResetOut
from app.seed import reset_and_seed

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset", response_model=ResetOut)
def reset_demo():
    """Drop every table and reload the deterministic demonstration data (saved actions are cleared)."""
    return {"status": "ok", **reset_and_seed()}
