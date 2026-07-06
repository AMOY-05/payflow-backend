from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.payout import (
    RouteRequest, RouteResponse,
    AllRoutesResponse, RouteResultOut
)
from app.services.routing_engine import get_best_route, get_all_routes

router = APIRouter(prefix="/api/v1/payout", tags=["Payout Routing"])


@router.post("/route", response_model=RouteResponse)
def get_recommended_route(
    data: RouteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    route = get_best_route(
        amount=data.amount,
        destination_country=data.destination_country,
        urgent=data.urgent,
        preferred_provider=data.preferred_provider
    )

    you_pay = data.amount + route.estimated_fee
    recipient_gets = data.amount - route.estimated_fee

    return RouteResponse(
        amount=data.amount,
        destination_country=data.destination_country,
        recommended_route=RouteResultOut(
            provider=route.provider,
            method=route.method,
            estimated_fee=route.estimated_fee,
            fee_currency=route.fee_currency,
            estimated_delivery=route.estimated_delivery,
            delivery_note=route.delivery_note,
            reason=route.reason,
            is_recommended=route.is_recommended,
            provider_logo=route.provider_logo
        ),
        you_pay=you_pay,
        recipient_gets=recipient_gets
    )


@router.post("/routes/compare", response_model=AllRoutesResponse)
def compare_all_routes(
    data: RouteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    routes = get_all_routes(
        amount=data.amount,
        destination_country=data.destination_country
    )

    return AllRoutesResponse(
        amount=data.amount,
        destination_country=data.destination_country,
        total_providers=len(routes),
        routes=[
            RouteResultOut(
                provider=r.provider,
                method=r.method,
                estimated_fee=r.estimated_fee,
                fee_currency=r.fee_currency,
                estimated_delivery=r.estimated_delivery,
                delivery_note=r.delivery_note,
                reason=r.reason,
                is_recommended=r.is_recommended,
                provider_logo=r.provider_logo
            )
            for r in routes
        ]
    )