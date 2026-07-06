from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.ai import (
    ChatRequest, ChatResponse,
    InsightsResponse, MonthlySummaryResponse
)
from app.services.ai_service import (
    chat_with_ai,
    generate_insights,
    generate_monthly_summary
)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat with PayBot — your personal financial assistant.
    Ask about your balance, best withdrawal options,
    FX rates, fees, or anything about your account.
    """
    history = None
    if data.conversation_history:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in data.conversation_history
        ]

    response = chat_with_ai(
        db=db,
        user=current_user,
        message=data.message,
        conversation_history=history
    )

    return ChatResponse(
        response=response,
        user_name=current_user.full_name
    )


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI-generated financial insights for your dashboard.
    Includes balance health, fee optimization tips,
    and current FX rate opportunities.
    """
    return generate_insights(db, current_user)


@router.get("/summary", response_model=MonthlySummaryResponse)
def get_monthly_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a plain English summary of your financial activity
    for the current month.
    """
    return generate_monthly_summary(db, current_user)