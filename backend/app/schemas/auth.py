from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_strength(password: str) -> str:
    """Require at least one letter and one digit."""
    if not any(char.isalpha() for char in password):
        raise ValueError("Password must contain at least one letter.")

    if not any(char.isdigit() for char in password):
        raise ValueError("Password must contain at least one digit.")

    return password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=150)

    check_password = field_validator("password")(validate_password_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=1024)


class DemoLoginRequest(BaseModel):
    role: Literal["admin", "trainer", "student"]


class DemoAccount(BaseModel):
    role: str
    email: str
    full_name: str


class DemoAccountsResponse(BaseModel):
    enabled: bool
    accounts: list[DemoAccount]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(max_length=2048)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(max_length=2048)
    new_password: str = Field(min_length=8, max_length=128)

    check_password = field_validator("new_password")(
        validate_password_strength
    )
