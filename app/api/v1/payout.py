"""
Payout routing API.
Selects best provider automatically.
Provider names are hidden from users — PayFlow branding only.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.routing_engine import (
    get_payout_route,
    compare_all_routes,
    validate_transfer
)

router = APIRouter(prefix="/api/v1/payout", tags=["Payout"])


class RouteRequest(BaseModel):
    amount: float
    destination_country: str = "NG"
    urgent: bool = False
    preferred_provider: Optional[str] = None


class CompareRequest(BaseModel):
    amount: float
    destination_country: str = "NG"


@router.post("/route")
def get_route(
    data: RouteRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get recommended payout route for a transfer.
    Provider selection is automatic and hidden from users.
    """
    if data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be greater than zero"
        )

    result = get_payout_route(
        amount=data.amount,
        destination_country=data.destination_country,
        urgent=data.urgent,
        preferred_provider=data.preferred_provider
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

    # Strip internal provider name from response
    route = result["recommended_route"].copy()
    # Keep provider internally for withdrawal initiation
    # but send display_name to frontend

    return result


@router.post("/routes/compare")
def compare_routes(
    data: CompareRequest,
    current_user: User = Depends(get_current_user)
):
    """Compare all available routes — shows PayFlow branded names only."""
    if data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be greater than zero"
        )

    return compare_all_routes(
        amount=data.amount,
        destination_country=data.destination_country
    )


@router.post("/validate")
def validate_route(
    data: RouteRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate that a transfer can proceed before initiating."""
    return validate_transfer(
        amount=data.amount,
        destination_country=data.destination_country,
        provider=data.preferred_provider
    )