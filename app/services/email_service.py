"""
Email service for sending verification emails.
Uses Gmail SMTP via fastapi-mail.
"""

import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.email_verification import EmailVerification
from app.models.user import User
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("fintech.email")


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send email via Resend API.
    More reliable than direct SMTP for production use.
    """
    # Try Resend first if configured
    resend_key = getattr(settings, 'RESEND_API_KEY', '')
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            resend.Emails.send({
                "from": "PayFlow <onboarding@resend.dev>",
                "to": to_email,
                "subject": subject,
                "html": html_content,
            })
            logger.info(f"Email sent via Resend to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Resend failed: {e}")

    # Fall back to Gmail SMTP
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        logger.warning("Email credentials not configured")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.MAIL_FROM
        msg["To"] = to_email
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_FROM, to_email, msg.as_string())

        logger.info(f"Email sent via SMTP to {to_email}")
        return True

    except Exception as e:
        logger.error(f"SMTP failed: {e}")
        return False


def create_verification_token(db: Session, user: User) -> str:
    """Create a secure email verification token."""
    # Delete any existing unused tokens for this user
    db.query(EmailVerification).filter(
        EmailVerification.user_id == user.id,
        EmailVerification.is_used == False
    ).delete()

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    verification = EmailVerification(
        user_id=user.id,
        token=token,
        is_used=False,
        expires_at=expires_at
    )
    db.add(verification)
    db.commit()
    return token


def send_verification_email(db: Session, user: User) -> bool:
    """Send email verification link to user."""
    token = create_verification_token(db, user)
    verification_url = (
        f"{settings.FRONTEND_URL}/verify-email?token={token}"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f9fafb;font-family:Inter,system-ui,sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <div style="background:#7c3aed;padding:40px;text-align:center;">
                <div style="width:48px;height:48px;background:rgba(255,255,255,0.2);border-radius:12px;display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px;">
                    <span style="color:white;font-size:24px;font-weight:bold;">P</span>
                </div>
                <h1 style="color:white;margin:0;font-size:24px;font-weight:700;">PayFlow</h1>
                <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:14px;">
                    USD Accounts for African Creators
                </p>
            </div>

            <div style="padding:40px;">
                <h2 style="color:#111827;font-size:20px;margin:0 0 8px;">
                    Verify your email address
                </h2>
                <p style="color:#6b7280;font-size:14px;line-height:1.6;margin:0 0 24px;">
                    Hi {user.full_name.split()[0]}, welcome to PayFlow!
                    Please verify your email address to activate your account
                    and access your USD virtual account.
                </p>

                <a href="{verification_url}"
                   style="display:block;background:#7c3aed;color:white;text-align:center;padding:16px 32px;border-radius:12px;text-decoration:none;font-weight:600;font-size:16px;margin-bottom:24px;">
                    Verify Email Address
                </a>

                <div style="background:#f9fafb;border-radius:12px;padding:16px;margin-bottom:24px;">
                    <p style="color:#6b7280;font-size:12px;margin:0 0 8px;">
                        Or copy this link into your browser:
                    </p>
                    <p style="color:#7c3aed;font-size:12px;word-break:break-all;margin:0;">
                        {verification_url}
                    </p>
                </div>

                <p style="color:#9ca3af;font-size:12px;margin:0;">
                    This link expires in 24 hours. If you did not create a
                    PayFlow account, you can safely ignore this email.
                </p>
            </div>

            <div style="background:#f9fafb;padding:24px;text-align:center;border-top:1px solid #e5e7eb;">
                <p style="color:#9ca3af;font-size:12px;margin:0;">
                    © 2026 PayFlow. Built for African creators.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(
        to_email=user.email,
        subject="Verify your PayFlow email address",
        html_content=html_content
    )


def verify_email_token(db: Session, token: str) -> User:
    """Verify email token and activate user account."""
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == token,
        EmailVerification.is_used == False
    ).first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link."
        )

    if datetime.now(timezone.utc) > verification.expires_at.replace(
        tzinfo=timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link has expired. Please request a new one."
        )

    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    user.is_email_verified = True
    verification.is_used = True
    db.add(user)
    db.add(verification)
    db.commit()

    return user


def send_kyc_status_email(
    user: User,
    status_type: str,
    reason: str = None
) -> bool:
    """Send KYC approval or rejection email."""
    if status_type == "approved":
        subject = "✅ Your KYC has been approved — PayFlow"
        body = f"""
        <p>Hi {user.full_name.split()[0]},</p>
        <p>Great news! Your identity verification (KYC) has been
        <strong style="color:#16a34a;">approved</strong>.</p>
        <p>You now have access to:</p>
        <ul>
            <li>Unlimited withdrawal amounts</li>
            <li>Faster payout processing</li>
            <li>Full platform features</li>
        </ul>
        <p>Log in to your PayFlow account to start withdrawing.</p>
        """
    else:
        subject = "❌ KYC verification update — PayFlow"
        body = f"""
        <p>Hi {user.full_name.split()[0]},</p>
        <p>Unfortunately, your KYC submission was
        <strong style="color:#dc2626;">not approved</strong>.</p>
        <p><strong>Reason:</strong> {reason or "Document could not be verified"}</p>
        <p>Please resubmit with a clearer image of your document.
        Make sure all corners are visible and the text is readable.</p>
        <a href="{settings.FRONTEND_URL}/profile"
           style="display:inline-block;background:#7c3aed;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:16px;">
            Resubmit KYC
        </a>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f9fafb;font-family:Inter,system-ui,sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;">
            <div style="background:#7c3aed;padding:32px;text-align:center;">
                <span style="color:white;font-size:20px;font-weight:bold;">PayFlow</span>
            </div>
            <div style="padding:32px;">
                {body}
                <p style="color:#9ca3af;font-size:12px;margin-top:24px;">
                    © 2026 PayFlow. Built for African creators.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(
        to_email=user.email,
        subject=subject,
        html_content=html_content
    )

def create_password_reset_token(db: Session, user: User) -> str:
    """Create a secure password reset token."""
    from app.models.security import PasswordResetToken

    # Delete any existing unused tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False
    ).delete()

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        is_used=False,
        expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    return token


def send_password_reset_email(db: Session, user: User) -> bool:
    """Send password reset link to user's email."""
    token = create_password_reset_token(db, user)
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f9fafb;font-family:Inter,system-ui,sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <div style="background:#7c3aed;padding:40px;text-align:center;">
                <div style="width:48px;height:48px;background:rgba(255,255,255,0.2);border-radius:12px;display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px;">
                    <span style="color:white;font-size:24px;font-weight:bold;">P</span>
                </div>
                <h1 style="color:white;margin:0;font-size:24px;font-weight:700;">PayFlow</h1>
                <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:14px;">
                    USD Accounts for African Creators
                </p>
            </div>

            <div style="padding:40px;">
                <h2 style="color:#111827;font-size:20px;margin:0 0 8px;">
                    Reset your password
                </h2>
                <p style="color:#6b7280;font-size:14px;line-height:1.6;margin:0 0 24px;">
                    Hi {user.full_name.split()[0]}, we received a request to reset
                    your PayFlow password. Click the button below to choose a new password.
                </p>

                <a href="{reset_url}"
                   style="display:block;background:#7c3aed;color:white;text-align:center;padding:16px 32px;border-radius:12px;text-decoration:none;font-weight:600;font-size:16px;margin-bottom:24px;">
                    Reset Password
                </a>

                <div style="background:#f9fafb;border-radius:12px;padding:16px;margin-bottom:24px;">
                    <p style="color:#6b7280;font-size:12px;margin:0 0 8px;">
                        Or copy this link into your browser:
                    </p>
                    <p style="color:#7c3aed;font-size:12px;word-break:break-all;margin:0;">
                        {reset_url}
                    </p>
                </div>

                <div style="background:#fef9c3;border-radius:12px;padding:16px;margin-bottom:24px;">
                    <p style="color:#854d0e;font-size:12px;margin:0;">
                        ⚠ This link expires in <strong>1 hour</strong>.
                        If you did not request a password reset, please ignore
                        this email. Your account remains secure.
                    </p>
                </div>

                <p style="color:#9ca3af;font-size:12px;margin:0;">
                    For security, never share this link with anyone.
                    PayFlow staff will never ask for your reset link.
                </p>
            </div>

            <div style="background:#f9fafb;padding:24px;text-align:center;border-top:1px solid #e5e7eb;">
                <p style="color:#9ca3af;font-size:12px;margin:0;">
                    © 2026 PayFlow. Built for African creators.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(
        to_email=user.email,
        subject="Reset your PayFlow password",
        html_content=html_content
    )


def verify_password_reset_token(db: Session, token: str) -> User:
    """Verify reset token and return user."""
    from app.models.security import PasswordResetToken

    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.is_used == False
    ).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link."
        )

    if datetime.now(timezone.utc) > reset_token.expires_at.replace(
        tzinfo=timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link has expired. Please request a new one."
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    return user, reset_token


def complete_password_reset(
    db: Session,
    token: str,
    new_password: str
) -> dict:
    """Complete password reset with new password."""
    from app.core.security import hash_password

    user, reset_token = verify_password_reset_token(db, token)

    # Validate password strength
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters."
        )
    if not any(c.isupper() for c in new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter."
        )
    if not any(c.isdigit() for c in new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number."
        )

    # Update password
    user.hashed_password = hash_password(new_password)
    reset_token.is_used = True

    db.add(user)
    db.add(reset_token)
    db.commit()

    return {
        "message": (
            "Password reset successfully. "
            "You can now log in with your new password."
        )
    }