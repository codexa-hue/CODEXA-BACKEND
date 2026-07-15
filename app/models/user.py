from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"

class User(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    hashed_password: str
    role: UserRole = UserRole.MEMBER
    is_active: bool = True
    unique_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Pydantic schemas for request/response validation
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    is_active: bool
    unique_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
