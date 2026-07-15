from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Resource(BaseModel):
    id: Optional[str] = None
    title: str
    category: str
    url: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ResourceCreate(BaseModel):
    title: str
    category: str
    url: str
    description: Optional[str] = None

class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None

class ResourceResponse(BaseModel):
    id: str
    title: str
    category: str
    url: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
