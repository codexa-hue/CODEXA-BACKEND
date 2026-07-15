from typing import List, Optional
from pydantic import BaseModel

class LeaderboardEntry(BaseModel):
    rank: int
    member_id: str
    name: str
    points: int
    role: str
    avatar_url: Optional[str] = None

class LeaderboardResponse(BaseModel):
    rankings: List[LeaderboardEntry]
