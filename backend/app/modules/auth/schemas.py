from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
import re


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    organization: str | None = None
    role: str = "STUDENT"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    organization: str | None
    role: str
    preferred_language: str
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
