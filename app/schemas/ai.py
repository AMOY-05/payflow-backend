from typing import Optional, List
from pydantic import BaseModel
from decimal import Decimal


class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    user_name: str


class InsightItem(BaseModel):
    type: str       # info, warning, opportunity, tip, action
    title: str
    message: str


class InsightsResponse(BaseModel):
    balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    total_fees_paid: Decimal
    total_withdrawals: int
    most_used_provider: str
    current_ngn_rate: Decimal
    insights: List[InsightItem]


class MonthlySummaryResponse(BaseModel):
    month: str
    summary: str
    stats: dict