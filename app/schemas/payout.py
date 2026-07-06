from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    destination_country: str = Field(..., min_length=2, max_length=2)
    urgent: bool = False
    preferred_provider: Optional[str] = None


class RouteResultOut(BaseModel):
    provider: str
    method: str
    estimated_fee: Decimal
    fee_currency: str
    estimated_delivery: str
    delivery_note: str
    reason: str
    is_recommended: bool
    provider_logo: str


class RouteResponse(BaseModel):
    amount: Decimal
    destination_country: str
    recommended_route: RouteResultOut
    you_pay: Decimal
    recipient_gets: Decimal


class AllRoutesResponse(BaseModel):
    amount: Decimal
    destination_country: str
    total_providers: int
    routes: List[RouteResultOut]