from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class SocialLinks(BaseModel):
    github: Optional[str] = ""
    linkedin: Optional[str] = ""
    twitter: Optional[str] = ""
    portfolio: Optional[str] = ""
    leetcode: Optional[str] = ""

class ActivityEntry(BaseModel):
    date: str          # ISO date string "YYYY-MM-DD"
    count: int = 0     # activity count that day

class PointAwardEntry(BaseModel):
    date: str                                      # "YYYY-MM-DD"
    points: int
    reason: str                                    # e.g. "Attended React Workshop"
    activity_type: str = "general"                 # workshop | hackathon | project | event | general
    awarded_by: str = "Admin"

class Badge(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    earned_at: datetime = Field(default_factory=datetime.utcnow)

class Member(BaseModel):
    id: Optional[str] = None
    user_id: Optional[str] = None
    unique_id: Optional[str] = None
    name: str
    role: str = "Member"
    year: str
    skills: List[str] = []
    socials: SocialLinks = Field(default_factory=SocialLinks)
    avatar_url: Optional[str] = None
    points: int = 0
    points_history: List[PointAwardEntry] = []   # audit trail of every award
    activity_log: List[ActivityEntry] = []        # heatmap data
    badges: List[Badge] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

# API schemas
class MemberCreate(BaseModel):
    name: str
    role: Optional[str] = "Member"
    year: str
    skills: Optional[List[str]] = []
    socials: Optional[SocialLinks] = None
    avatar_url: Optional[str] = None
    points: Optional[int] = 0

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    year: Optional[str] = None
    skills: Optional[List[str]] = None
    socials: Optional[SocialLinks] = None
    avatar_url: Optional[str] = None
    points: Optional[int] = None

class AwardPointsRequest(BaseModel):
    points: int
    reason: str
    activity_type: str = "general"    # workshop | hackathon | project | event | general
    awarded_by: Optional[str] = "Admin"

class ActivityLogRequest(BaseModel):
    date: str
    count: int = 1

class MemberResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    unique_id: Optional[str] = None
    name: str
    role: str
    year: str
    skills: List[str]
    socials: SocialLinks
    avatar_url: Optional[str]
    points: int
    points_history: List[PointAwardEntry] = []
    activity_log: List[ActivityEntry] = []
    badges: List[Badge] = []
    created_at: datetime

    class Config:
        from_attributes = True
