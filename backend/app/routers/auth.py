from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.schemas.auth import (
    DemoAccountsResponse,
    DemoLoginRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserResponse
from app.services import email_service
from app.services.auth_service import (
    authenticate_user,
    create_email_verification_token,
    get_demo_accounts,
    get_demo_user,
    issue_tokens,
    register_user,
    request_password_reset,
    reset_password,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_email,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register"))],
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new student account."""

    try:
        user = register_user(
            db=db,
            email=data.email,
            password=data.password,
            full_name=data.full_name,
            role="student",
        )
        email_service.send_verification_email(
            user.email,
            create_email_verification_token(user),
        )
        return user

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("login"))],
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a user and issue tokens."""

    user = authenticate_user(
        db=db,
        email=data.email,
        password=data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return issue_tokens(db, user)


def demo_login_allowed() -> bool:
    """Demo login is never served in production, even if the flag is set
    after startup (startup validation already rejects that combination)."""
    return settings.demo_login_enabled and settings.app_env != "production"


@router.get(
    "/demo",
    response_model=DemoAccountsResponse,
)
def list_demo_accounts(
    db: Session = Depends(get_db),
):
    """List the demo accounts available for one-click sign-in."""

    if not demo_login_allowed():
        return {"enabled": False, "accounts": []}

    return {"enabled": True, "accounts": get_demo_accounts(db)}


@router.post(
    "/demo-login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("demo-login"))],
)
def demo_login(
    data: DemoLoginRequest,
    db: Session = Depends(get_db),
):
    """Sign in to a seeded demo account without a password (development only)."""

    if not demo_login_allowed():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo login is disabled.",
        )

    user = get_demo_user(db, data.role)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The demo account has not been seeded. Run scripts/seed.py.",
        )

    return issue_tokens(db, user)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user's profile."""

    return current_user


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("refresh"))],
)
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate a refresh token and issue new tokens."""

    tokens = rotate_refresh_token(
        db=db,
        submitted_token=data.refresh_token,
    )

    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked refresh token.",
        )

    return tokens

@router.post("/logout")
def logout(
    data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log out by revoking the current refresh token."""

    revoked = revoke_refresh_token(
        db=db,
        submitted_token=data.refresh_token,
        user_id=current_user.id,
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    return {"message": "Successfully logged out."}


@router.post(
    "/verify-email/request",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("verify-email-request"))],
)
def request_email_verification(
    current_user: User = Depends(get_current_user),
):
    """Issue a new email verification token for the current user."""

    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    email_service.send_verification_email(
        current_user.email,
        create_email_verification_token(current_user),
    )

    return {"message": "Verification email requested."}


@router.post("/verify-email")
def confirm_email_verification(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """Verify an email address with a verification token."""

    if not verify_email(db, data.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used verification token.",
        )

    return {"message": "Email verified successfully."}


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("password-reset-request"))],
)
def request_password_reset_token(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Request a password reset without revealing whether the email exists."""

    result = request_password_reset(db, data.email)

    if result is not None:
        user, token = result
        email_service.send_password_reset_email(user.email, token)

    return {
        "message": (
            "If an account exists for this email, "
            "a password reset link will be issued."
        )
    }


@router.post(
    "/password-reset/confirm",
    dependencies=[Depends(rate_limit("password-reset-confirm"))],
)
def confirm_password_reset(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Set a new password using a valid reset token."""

    if not reset_password(db, data.token, data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used reset token.",
        )

    return {"message": "Password has been reset successfully."}