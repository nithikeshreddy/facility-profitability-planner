from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.rules.types import Overrides
from app.schemas import ActionIn, ActionOut

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("", response_model=ActionOut, status_code=201)
def save_action(body: ActionIn, db: Session = Depends(get_db)):
    """Save a proposed action. The projection is re-computed on the server, never taken from the client."""
    overrides = Overrides(**body.overrides.model_dump()) if body.overrides else None
    try:
        return services.save_action(db, body.location_id, body.plan_type, body.offer_id, body.fix_id, overrides, body.note)
    except services.NotFound as e:
        raise HTTPException(404, str(e))
    except services.NotFeasible as e:
        raise HTTPException(422, str(e))


@router.get("", response_model=list[ActionOut])
def list_actions(location_id: int | None = None, db: Session = Depends(get_db)):
    return services.list_actions(db, location_id)
