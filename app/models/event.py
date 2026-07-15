from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Event(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    date: datetime
    location: str
    registration_link: Optional[str] = None
    google_form_url: Optional[str] = None          # Google Form link for registration
    registered_users: List[str] = []  # User IDs
    form_submitted_users: List[str] = [] # User IDs of members who filled the form
    attended_users: List[str] = []    # User IDs of members who attended
    max_seats: Optional[int] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EventCreate(BaseModel):
    title: str
    description: str
    date: datetime
    location: str
    registration_link: Optional[str] = None
    google_form_url: Optional[str] = None
    max_seats: Optional[int] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[datetime] = None
    location: Optional[str] = None
    registration_link: Optional[str] = None
    google_form_url: Optional[str] = None
    max_seats: Optional[int] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None

class EventResponse(BaseModel):
    id: str
    title: str
    description: str
    date: datetime
    location: str
    registration_link: Optional[str]
    google_form_url: Optional[str] = None
    registered_users: List[str]
    form_submitted_users: List[str] = []
    attended_users: List[str] = []
    max_seats: Optional[int]
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
