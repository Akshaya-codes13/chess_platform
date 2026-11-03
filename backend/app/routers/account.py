"""Account settings for every signed-in user, whatever their role."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.account import AccountSettings, AccountSettingsUpdate, PasswordChange
from app.services import account_service

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("/settings", response_model=AccountSettings)
def get_settings(user: User = Depends(get_current_user)):
    return account_service.get_settings(user)


@router.patch("/settings", response_model=AccountSettings)
def update_settings(
    data: AccountSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partial update. Role, email and status are not editable here."""
    return account_service.update_settings(db, user, data.model_dump(exclude_unset=True))


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the password; every refresh token is revoked, so other devices
    must sign in again."""
    account_service.change_password(db, user, data.current_password, data.new_password)
