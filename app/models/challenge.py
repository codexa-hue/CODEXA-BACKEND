from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class Challenge(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    difficulty: str  # Easy | Medium | Hard
    link: Optional[str] = None
    points: int = 10
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChallengeCreate(BaseModel):
    title: str
    description: str
    difficulty: str
    link: Optional[str] = None
    points: int = 10

class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    difficulty: Optional[str] = None
    link: Optional[str] = None
    points: Optional[int] = None

class ChallengeResponse(BaseModel):
    id: str
    title: str
    description: str
    difficulty: str
    link: Optional[str]
    points: int
    created_at: datetime

    class Config:
        from_attributes = True

class ChallengeSubmission(BaseModel):
    id: Optional[str] = None
    challenge_id: str
    challenge_title: str
    user_id: str
    student_name: str
    github_url: str
    comments: Optional[str] = None
    feedback: Optional[str] = None
    status: str = "Pending"  # Pending | Approved | Rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChallengeSubmissionResponse(BaseModel):
    id: str
    challenge_id: str
    challenge_title: str
    user_id: str
    student_name: str
    github_url: str
    comments: Optional[str]
    feedback: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SubmissionStatusRequest(BaseModel):
    status: str  # Approved | Rejected
    feedback: Optional[str] = None

