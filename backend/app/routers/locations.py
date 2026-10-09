from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.rules.types import Overrides
from app.schemas import LocationDetailOut, PlanComparisonOut, PlanOverridesIn

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("/{location_id}", response_model=LocationDetailOut)
def location_detail(location_id: int, db: Session = Depends(get_db)):
    try:
        return services.location_detail(db, location_id)
    except services.NotFound as e:
        raise HTTPException(404, str(e))


@router.post("/{location_id}/plans", response_model=PlanComparisonOut)
def compare_plans(location_id: int, overrides: PlanOverridesIn | None = None, db: Session = Depends(get_db)):
    try:
        return services.plan_workbench(db, location_id, Overrides(**overrides.model_dump()) if overrides else None)
    except services.NotFound as e:
        raise HTTPException(404, str(e))
    except services.InvalidOverrides as e:
        raise HTTPException(422, str(e))
