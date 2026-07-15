from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Announcement(BaseModel):
    id: Optional[str] = None
    title: str
    content: str
    author: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    expires_at: Optional[datetime] = None          # Auto-hide after this date
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AnnouncementCreate(BaseModel):
    title: str
    content: str
    author: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    expires_at: Optional[datetime] = None

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    expires_at: Optional[datetime] = None

class AnnouncementResponse(BaseModel):
    id: str
    title: str
    content: str
    author: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
