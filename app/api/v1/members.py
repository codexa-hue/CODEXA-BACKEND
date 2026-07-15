from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from datetime import date
from typing import List
from app.api.deps import get_current_active_user, get_current_admin
from app.models.user import User, UserRole
from app.models.member import (
    Member, MemberCreate, MemberUpdate, MemberResponse,
    ActivityEntry, Badge, AwardPointsRequest, PointAwardEntry,
)
from app.core.email import send_points_awarded
from app.core.database import get_db

router = APIRouter()

# ── Badge definitions ─────────────────────────────────────────────
# Only earned by COMPLETING workshops, hackathons, or projects.
# No badges for joining, attending, or profile completion.

WORKSHOP_BADGES = [
    {"id": "workshop_1",  "name": "Workshop Graduate",   "description": "Completed your first workshop",         "icon": "🎖️"},
    {"id": "workshop_3",  "name": "Workshop Specialist",  "description": "Completed 3 workshops",                "icon": "📜"},
    {"id": "workshop_5",  "name": "Workshop Expert",      "description": "Completed 5 workshops",                "icon": "🏅"},
    {"id": "workshop_10", "name": "Workshop Mentor",      "description": "Completed 10 workshops",               "icon": "🎗️"},
]

HACKATHON_BADGES = [
    {"id": "hackathon_1",  "name": "Code Sprinter",       "description": "Completed your first hackathon",       "icon": "⚡"},
    {"id": "hackathon_3",  "name": "Hack Enthusiast",     "description": "Completed 3 hackathons",               "icon": "🔬"},
    {"id": "hackathon_5",  "name": "Hackathon Champion",  "description": "Completed 5 hackathons",               "icon": "🥇"},
]

PROJECT_BADGES = [
    {"id": "project_1",  "name": "Project Starter",      "description": "Completed your first club project",    "icon": "🔩"},
    {"id": "project_3",  "name": "Project Builder",      "description": "Completed 3 club projects",            "icon": "⚙️"},
    {"id": "project_5",  "name": "Project Architect",    "description": "Completed 5 club projects",            "icon": "🏗️"},
]

ALL_BADGES = WORKSHOP_BADGES + HACKATHON_BADGES + PROJECT_BADGES


def _count_activity_type(member: Member, activity_type: str) -> int:
    """Count point award entries of a given activity_type."""
    return sum(1 for e in member.points_history if e.activity_type == activity_type)


def check_and_award_badges(member: Member) -> List[Badge]:
    """
    Badges are ONLY awarded when a member completes workshops,
    hackathons, or projects. No badges for joining or attending.
    """
    existing_ids = {b.id for b in member.badges}
    new_badges   = []
    workshops    = _count_activity_type(member, "workshop")
    hackathons   = _count_activity_type(member, "hackathon")
    projects     = _count_activity_type(member, "project")

    checks = {
        "workshop_1":    workshops  >= 1,
        "workshop_3":    workshops  >= 3,
        "workshop_5":    workshops  >= 5,
        "workshop_10":   workshops  >= 10,
        "hackathon_1":   hackathons >= 1,
        "hackathon_3":   hackathons >= 3,
        "hackathon_5":   hackathons >= 5,
        "project_1":     projects   >= 1,
        "project_3":     projects   >= 3,
        "project_5":     projects   >= 5,
    }

    for bd in ALL_BADGES:
        if bd["id"] in existing_ids:
            continue
        if checks.get(bd["id"], False):
            new_badges.append(Badge(**bd))

    return new_badges


@router.get("/", response_model=List[MemberResponse])
async def read_members(limit: int = 100, offset: int = 0):
    db = get_db()
    members_ref = db.collection("members")
    docs = members_ref.get()
    
    members = [Member(id=doc.id, **doc.to_dict()) for doc in docs]
    members = [m for m in members if m.role.lower() != "admin"]
    # Slice members
    members = members[offset : offset + limit]
    
    # Batch query all user documents to fetch unique_ids efficiently
    users_docs = db.collection("users").get()
    user_unique_ids = {u_doc.id: u_doc.to_dict().get("unique_id") for u_doc in users_docs}
    
    valid_ids = {bd["id"] for bd in ALL_BADGES}
    for member in members:
        if member.user_id:
            member.unique_id = user_unique_ids.get(member.user_id)
            
        original_count = len(member.badges)
        member.badges = [b for b in member.badges if b.id in valid_ids]
        new_badges = check_and_award_badges(member)
        member.badges.extend(new_badges)
        if len(member.badges) != original_count or new_badges:
            members_ref.document(member.id).set(member.model_dump(exclude={"id"}))
            
    return members


@router.get("/{id}", response_model=MemberResponse)
async def read_member(id: str):
    db = get_db()
    doc = db.collection("members").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member profile not found")

    member = Member(id=doc.id, **doc.to_dict())

    # Strip any badges whose IDs are no longer in the current badge set
    valid_ids = {bd["id"] for bd in ALL_BADGES}
    original_count = len(member.badges)
    member.badges = [b for b in member.badges if b.id in valid_ids]

    # Re-check and award any badges now deserved under the new rules
    new_badges = check_and_award_badges(member)
    member.badges.extend(new_badges)

    if len(member.badges) != original_count or new_badges:
        db.collection("members").document(member.id).set(member.model_dump(exclude={"id"}))

    if member.user_id:
        user_doc = db.collection("users").document(member.user_id).get()
        if user_doc.exists:
            member.unique_id = user_doc.to_dict().get("unique_id")

    return member


@router.post("/", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(member_in: MemberCreate, current_user: User = Depends(get_current_admin)):
    db = get_db()
    member = Member(**member_in.model_dump())
    # Award the welcome badge on creation
    new_badges = check_and_award_badges(member)
    member.badges.extend(new_badges)
    
    doc_ref = db.collection("members").document()
    doc_ref.set(member.model_dump(exclude={"id"}))
    member.id = doc_ref.id
    
    if member.user_id:
        user_doc = db.collection("users").document(member.user_id).get()
        if user_doc.exists:
            member.unique_id = user_doc.to_dict().get("unique_id")
            
    return member


@router.put("/{id}", response_model=MemberResponse)
async def update_member(id: str, member_in: MemberUpdate, current_user: User = Depends(get_current_active_user)):
    db = get_db()
    doc = db.collection("members").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member profile not found")
        
    member = Member(id=doc.id, **doc.to_dict())
    
    if member.user_id != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    update_data = member_in.model_dump(exclude_unset=True)
    # Non-admins cannot set points directly
    if current_user.role != UserRole.ADMIN:
        update_data.pop("points", None)

    for field, value in update_data.items():
        setattr(member, field, value)

    new_badges = check_and_award_badges(member)
    member.badges.extend(new_badges)
    
    db.collection("members").document(member.id).set(member.model_dump(exclude={"id"}))
    
    if member.user_id:
        user_doc = db.collection("users").document(member.user_id).get()
        if user_doc.exists:
            member.unique_id = user_doc.to_dict().get("unique_id")
            
    return member


@router.post("/{id}/award_points", response_model=MemberResponse)
async def award_points(
    id: str,
    req: AwardPointsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
):
    """Admin awards points with reason, sends email notification."""
    db = get_db()
    doc = db.collection("members").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        
    member = Member(id=doc.id, **doc.to_dict())

    today_str = date.today().strftime("%Y-%m-%d")

    member.points_history.append(PointAwardEntry(
        date=today_str,
        points=req.points,
        reason=req.reason,
        activity_type=req.activity_type,
        awarded_by=req.awarded_by,
    ))

    existing = next((e for e in member.activity_log if e.date == today_str), None)
    if existing:
        existing.count += 1
    else:
        member.activity_log.append(ActivityEntry(date=today_str, count=1))

    member.points += req.points

    new_badges = check_and_award_badges(member)
    member.badges.extend(new_badges)

    db.collection("members").document(member.id).set(member.model_dump(exclude={"id"}))

    # Send email notification in background
    if member.user_id:
        try:
            user_doc = db.collection("users").document(member.user_id).get()
            if user_doc.exists:
                user_obj = User(id=user_doc.id, **user_doc.to_dict())
                if user_obj.email:
                    badge_dicts = [{"id": b.id, "name": b.name, "description": b.description, "icon": b.icon}
                                   for b in new_badges]
                    background_tasks.add_task(
                        send_points_awarded,
                        to_email=str(user_obj.email),
                        name=member.name,
                        points=req.points,
                        reason=req.reason,
                        activity_type=req.activity_type,
                        total_points=member.points,
                        new_badges=badge_dicts,
                    )
        except Exception:
            pass

    if member.user_id:
        user_doc = db.collection("users").document(member.user_id).get()
        if user_doc.exists:
            member.unique_id = user_doc.to_dict().get("unique_id")

    return member


@router.delete("/{id}/points_history/{entry_idx}", response_model=MemberResponse)
async def remove_points_entry(
    id: str,
    entry_idx: int,
    current_user: User = Depends(get_current_admin),
):
    """Remove a specific points history entry and deduct its points. Admin only."""
    db = get_db()
    doc = db.collection("members").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        
    member = Member(id=doc.id, **doc.to_dict())
    
    if entry_idx < 0 or entry_idx >= len(member.points_history):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entry index")

    entry = member.points_history.pop(entry_idx)
    member.points = max(0, member.points - entry.points)
    
    db.collection("members").document(member.id).set(member.model_dump(exclude={"id"}))
    
    if member.user_id:
        user_doc = db.collection("users").document(member.user_id).get()
        if user_doc.exists:
            member.unique_id = user_doc.to_dict().get("unique_id")
            
    return member


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(id: str, current_user: User = Depends(get_current_active_user)):
    db = get_db()
    doc = db.collection("members").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member profile not found")
        
    member = Member(id=doc.id, **doc.to_dict())
    
    if member.user_id != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        
    db.collection("members").document(member.id).delete()
    return None
