from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.schemas import RenewalQueueOut

router = APIRouter(prefix="/api/renewals", tags=["renewals"])


@router.get("", response_model=RenewalQueueOut)
def renewal_queue(db: Session = Depends(get_db)):
    """Contracts to review before renewal, sorted by renewal date, then by the largest monthly gap."""
    return services.renewal_view(db)
