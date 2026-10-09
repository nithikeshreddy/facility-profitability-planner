from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.rules.incentives import ResultChange
from app.schemas import SimulateIn, SimulationOut, VendorIncentivesOut

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get("/incentives", response_model=VendorIncentivesOut)
def vendor_incentives(db: Session = Depends(get_db)):
    return services.vendor_incentives(db)


@router.post("/{vendor_id}/simulate", response_model=SimulationOut)
def simulate(vendor_id: int, body: SimulateIn, db: Session = Depends(get_db)):
    """Recalculate eligibility and contribution with one service result changed. Nothing is saved."""
    try:
        return services.simulate_incentive(db, vendor_id, ResultChange(**body.model_dump()))
    except services.NotFound as e:
        raise HTTPException(404, str(e))
