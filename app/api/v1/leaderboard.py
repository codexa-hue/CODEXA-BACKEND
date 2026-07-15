from fastapi import APIRouter
from app.models.leaderboard import LeaderboardResponse, LeaderboardEntry
from app.models.member import Member
from app.core.database import get_db
from firebase_admin import firestore

router = APIRouter()

@router.get("/", response_model=LeaderboardResponse)
async def read_leaderboard(limit: int = 50):
    """
    Get the club leaderboard ranks, ordered by member points descending.
    """
    db = get_db()
    
    # Fetch members sorted by points (descending)
    docs = db.collection("members")\
             .order_by("points", direction=firestore.Query.DESCENDING)\
             .limit(limit)\
             .get()
             
    members = [Member(id=doc.id, **doc.to_dict()) for doc in docs]
    members = [m for m in members if m.role.lower() != "admin"]
    
    rankings = []
    for index, member in enumerate(members):
        rankings.append(
            LeaderboardEntry(
                rank=index + 1,
                member_id=str(member.id),
                name=member.name,
                points=member.points,
                role=member.role,
                avatar_url=member.avatar_url
            )
        )
        
    return LeaderboardResponse(rankings=rankings)
