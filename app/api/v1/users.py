from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut, UserProfileUpdate, ChangePasswordRequest
from app.services.user_service import (
    update_user_profile,
    change_user_password,
    delete_user_account
)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


class DeleteAccountRequest(BaseModel):
    password: str
    confirmation: str  # must equal "DELETE MY ACCOUNT"


@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserOut)
def update_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_user_profile(db, current_user, data)


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return change_user_password(db, current_user, data)


@router.delete("/delete-account")
def delete_account(
    data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete account.
    Requires password confirmation and typing DELETE MY ACCOUNT.
    """
    if data.confirmation != "DELETE MY ACCOUNT":
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please type DELETE MY ACCOUNT exactly to confirm deletion."
        )
    return delete_user_account(db, current_user, data.password)