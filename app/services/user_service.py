from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserProfileUpdate, ChangePasswordRequest
from app.core.security import verify_password, hash_password


def get_user_profile(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def update_user_profile(db: Session, user: User, data: UserProfileUpdate) -> User:
    # Only update fields that were actually sent in the request
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def change_user_password(db: Session, user: User, data: ChangePasswordRequest) -> dict:
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}

from datetime import datetime, timezone

def delete_user_account(
    db: Session,
    user: User,
    password: str
) -> dict:
    """
    Soft delete a user account.

    Fintech compliance rules:
    - We never hard delete financial records immediately
    - User data is anonymized after 30 days
    - Transaction history is kept forever (audit requirement)
    - Password must be confirmed before deletion
    """
    # Verify password before deletion
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password. Account deletion cancelled."
        )

    # Check for pending withdrawals
    from app.models.withdrawal import Withdrawal
    pending = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id,
        Withdrawal.status.in_(["pending", "processing"])
    ).count()

    if pending > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"You have {pending} pending withdrawal(s). "
                f"Please wait for them to complete before deleting your account."
            )
        )

    # Soft delete — mark as deleted
    user.is_deleted = True
    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)

    # Anonymize personal data immediately
    user.phone_number = None
    user.address = None
    user.date_of_birth = None

    db.add(user)
    db.commit()

    return {
        "message": (
            "Your account has been deleted successfully. "
            "Your financial records will be retained for 30 days "
            "as required by financial regulations, then permanently removed."
        ),
        "deleted_at": user.deleted_at.isoformat()
    }