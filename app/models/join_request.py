from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class JoinRequest(BaseModel):
    id: Optional[str] = None
    name: str
    email: EmailStr
    year: str
    joining_year: int = Field(default_factory=lambda: datetime.utcnow().year)
    skills: List[str] = []
    reason_to_join: str
    hashed_password: Optional[str] = None   # None for legacy records created before this field existed
    status: RequestStatus = RequestStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ── Request / Response schemas ──────────────────────────────────

class JoinRequestCreate(BaseModel):
    name: str
    email: EmailStr
    year: str
    joining_year: int
    skills: Optional[List[str]] = []
    reason_to_join: str
    password: str = Field(..., min_length=6)   # plain-text; hashed before storing

class JoinRequestUpdateStatus(BaseModel):
    status: RequestStatus

class JoinRequestResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    year: str
    joining_year: int
    skills: List[str]
    reason_to_join: str
    status: RequestStatus
    created_at: datetime
    # hashed_password intentionally excluded from response

    class Config:
        from_attributes = True
