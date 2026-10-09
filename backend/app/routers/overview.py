from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.schemas import OverviewOut

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewOut)
def overview(
    state: str | None = None, loss_only: bool = False, detailed_only: bool = False, db: Session = Depends(get_db)
):
    return services.overview(db, state, loss_only, detailed_only)
