"""
Stores one-time password reset OTPs.
Each record expires after 15 minutes.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class PasswordResetOTP(BaseModel):
    id: Optional[str] = None
    email: str
    otp: str                  # 6-digit string
    used: bool = False
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return not self.used and now < expires


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., min_length=6)
