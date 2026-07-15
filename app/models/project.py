from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Project(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    contributors: List[str]  # Member IDs or names
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    tags: List[str] = []
    thumbnail_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ProjectCreate(BaseModel):
    title: str
    description: str
    contributors: List[str]
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    tags: Optional[List[str]] = []
    thumbnail_url: Optional[str] = None

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    contributors: Optional[List[str]] = None
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    tags: Optional[List[str]] = None
    thumbnail_url: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    contributors: List[str]
    github_url: Optional[str]
    live_url: Optional[str]
    tags: List[str]
    thumbnail_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
