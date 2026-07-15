from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
from pydantic import BaseModel
from app.api.deps import get_current_active_user, get_current_admin
from app.models.user import User
from app.models.event import Event, EventCreate, EventUpdate, EventResponse
from app.models.member import Member, PointAwardEntry, ActivityEntry
from app.api.v1.members import check_and_award_badges
from datetime import datetime, timezone, timedelta, date as py_date
from app.core.email import send_event_registration_confirmation, send_event_deleted_notification
from app.core.database import get_db

router = APIRouter()

# Events are considered expired 1 day after their date passes
EXPIRY_GRACE_HOURS = 24

def _is_expired(event: Event) -> bool:
    """Return True if the event date + grace period has passed."""
    event_dt = event.date
    now = datetime.now(timezone.utc)
    if event_dt.tzinfo is None:
        event_dt = event_dt.replace(tzinfo=timezone.utc)
    return now > event_dt + timedelta(hours=EXPIRY_GRACE_HOURS)


@router.get("/", response_model=List[EventResponse])
async def read_events(limit: int = 100, offset: int = 0):
    """
    Get list of active (non-expired) events. Accessible by anyone.
    Events are hidden 24 hours after their date passes.
    """
    db = get_db()
    docs = db.collection("events").get()
    all_events = [Event(id=doc.id, **doc.to_dict()) for doc in docs]
    active_events = [e for e in all_events if not _is_expired(e)]
    return active_events[offset : offset + limit]


@router.get("/admin/all", response_model=List[EventResponse])
async def read_all_events_admin(
    current_user: User = Depends(get_current_admin),
    limit: int = 100,
    offset: int = 0,
):
    """
    Get ALL events including expired/past ones. Admin only.
    """
    db = get_db()
    docs = db.collection("events").get()
    all_events = [Event(id=doc.id, **doc.to_dict()) for doc in docs]
    
    def get_event_date(e):
        d = e.date
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
        
    all_events.sort(key=get_event_date, reverse=True)
    return all_events[offset : offset + limit]


@router.get("/{id}", response_model=EventResponse)
async def read_event(id: str):
    """
    Get details of a specific event.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    return Event(id=doc.id, **doc.to_dict())


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    current_user: User = Depends(get_current_admin)
):
    """
    Create a new event. Restricted to Admins.
    """
    db = get_db()
    event = Event(**event_in.model_dump())
    
    doc_ref = db.collection("events").document()
    doc_ref.set(event.model_dump(exclude={"id"}))
    event.id = doc_ref.id
    
    return event


@router.put("/{id}", response_model=EventResponse)
async def update_event(
    id: str,
    event_in: EventUpdate,
    current_user: User = Depends(get_current_admin)
):
    """
    Update an event. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
        
    event = Event(id=doc.id, **doc.to_dict())
    update_data = event_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)
        
    db.collection("events").document(event.id).set(event.model_dump(exclude={"id"}))
    return event


@router.delete("/expired", status_code=status.HTTP_200_OK)
async def delete_expired_events(
    current_user: User = Depends(get_current_admin)
):
    """
    Permanently delete all expired events (past date + grace period). Admin only.
    """
    db = get_db()
    docs = db.collection("events").get()
    all_events = [Event(id=doc.id, **doc.to_dict()) for doc in docs]
    expired = [e for e in all_events if _is_expired(e)]
    for e in expired:
        db.collection("events").document(e.id).delete()
    return {"deleted": len(expired), "message": f"Removed {len(expired)} expired event(s)."}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin)
):
    """
    Delete an event. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    event = Event(id=doc.id, **doc.to_dict())
    
    # 1. Fetch active users and member names
    users_docs = db.collection("users").where("is_active", "==", True).get()
    users_list = [User(id=ud.id, **ud.to_dict()) for ud in users_docs]
    
    members_docs = db.collection("members").get()
    members_map = {
        str(m.to_dict().get("user_id")): m.to_dict().get("name") 
        for m in members_docs if m.to_dict().get("user_id")
    }
    
    # 2. Delete the event
    db.collection("events").document(id).delete()
    
    # 3. Dispatch emails in the background
    event_date_str = event.date.strftime("%A, %b %d, %Y at %I:%M %p")
    for user in users_list:
        name = members_map.get(str(user.id)) or user.email.split("@")[0].capitalize()
        background_tasks.add_task(
            send_event_deleted_notification,
            user.email,
            name,
            event.title,
            event_date_str
        )
        
    return None


@router.post("/{id}/register", response_model=EventResponse)
async def register_for_event(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Register the logged-in user for an event.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
        
    event = Event(id=doc.id, **doc.to_dict())
    user_id_str = str(current_user.id)
    
    if user_id_str in event.registered_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered for this event"
        )
        
    if event.max_seats is not None and len(event.registered_users) >= event.max_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event is fully booked"
        )
        
    event.registered_users.append(user_id_str)
    db.collection("events").document(event.id).set(event.model_dump(exclude={"id"}))

    # Send confirmation email in background ONLY if there is no Google Form
    if not event.google_form_url:
        member_docs = db.collection("members").where("user_id", "==", user_id_str).limit(1).get()
        member_doc = member_docs[0] if member_docs else None
        member = Member(id=member_doc.id, **member_doc.to_dict()) if member_doc else None
        
        name = member.name if member else current_user.email.split("@")[0].capitalize()
        event_date_str = event.date.strftime("%A, %b %d, %Y at %I:%M %p")
        background_tasks.add_task(
            send_event_registration_confirmation,
            current_user.email,
            name,
            event.title,
            event_date_str,
            event.location
        )

    return event


@router.post("/{id}/confirm-form", response_model=EventResponse)
async def confirm_form_submission(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Mark that the user has filled the Google Form for the event,
    and send the confirmation email.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
        
    event = Event(id=doc.id, **doc.to_dict())
    user_id_str = str(current_user.id)
    
    if user_id_str not in event.registered_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not registered for this event"
        )
        
    if user_id_str in event.form_submitted_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Form submission already confirmed"
        )
        
    event.form_submitted_users.append(user_id_str)
    db.collection("events").document(event.id).set(event.model_dump(exclude={"id"}))
    
    # Send confirmation email in background
    member_docs = db.collection("members").where("user_id", "==", user_id_str).limit(1).get()
    member_doc = member_docs[0] if member_docs else None
    member = Member(id=member_doc.id, **member_doc.to_dict()) if member_doc else None
    
    name = member.name if member else current_user.email.split("@")[0].capitalize()
    event_date_str = event.date.strftime("%A, %b %d, %Y at %I:%M %p")
    background_tasks.add_task(
        send_event_registration_confirmation,
        current_user.email,
        name,
        event.title,
        event_date_str,
        event.location
    )
    
    return event



@router.post("/{id}/unregister", response_model=EventResponse)
async def unregister_from_event(
    id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel the logged-in user's registration for an event.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
        
    event = Event(id=doc.id, **doc.to_dict())
    user_id_str = str(current_user.id)
    
    if user_id_str not in event.registered_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not registered for this event"
        )
        
    event.registered_users.remove(user_id_str)
    db.collection("events").document(event.id).set(event.model_dump(exclude={"id"}))
    return event


class RegisteredUserDetail(BaseModel):
    user_id: str
    name: str
    email: str
    year: str
    role: str
    points: int = 0
    problems_solved: int = 0
    streak_days: int = 0
    skills: List[str] = []
    attended: bool = False


@router.get("/{id}/registrations", response_model=List[RegisteredUserDetail])
async def get_event_registrations(
    id: str,
    current_user: User = Depends(get_current_admin)
):
    """
    Get full list of registered users for a specific event. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
        
    event = Event(id=doc.id, **doc.to_dict())
    
    details = []
    for user_id in event.registered_users:
        user_doc = db.collection("users").document(user_id).get()
        if not user_doc.exists:
            continue
        user = User(id=user_doc.id, **user_doc.to_dict())
        
        member_docs = db.collection("members").where("user_id", "==", user_id).limit(1).get()
        member_doc = member_docs[0] if member_docs else None
        member = Member(id=member_doc.id, **member_doc.to_dict()) if member_doc else None
        
        name = member.name if member else "Unknown"
        year = member.year if member else "Unknown"
        role = member.role if member else "Member"
        points = member.points if member else 0
        problems_solved = getattr(member, "problems_solved", 0) if member else 0
        streak_days = getattr(member, "streak_days", 0) if member else 0
        skills = member.skills if member else []
        
        details.append(RegisteredUserDetail(
            user_id=user_id,
            name=name,
            email=user.email,
            year=year,
            role=role,
            points=points,
            problems_solved=problems_solved,
            streak_days=streak_days,
            skills=skills,
            attended=user_id in event.attended_users
        ))
    return details

class UpdateAttendanceRequest(BaseModel):
    user_id: str
    attended: bool
    points: int = 10

@router.post("/{id}/attendance", status_code=status.HTTP_200_OK)
async def update_event_attendance(
    id: str,
    req: UpdateAttendanceRequest,
    current_user: User = Depends(get_current_admin)
):
    """
    Mark/unmark member attendance for a specific event. Restricted to Admins.
    Automatically increments/decrements club points.
    """
    db = get_db()
    
    # 1. Fetch Event
    doc = db.collection("events").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    event = Event(id=doc.id, **doc.to_dict())
    
    # Verify the user is registered
    if req.user_id not in event.registered_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member is not registered for this event"
        )

    # 2. Fetch Member
    member_docs = db.collection("members").where("user_id", "==", req.user_id).limit(1).get()
    if not member_docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member profile not found"
        )
    member_doc = member_docs[0]
    member = Member(id=member_doc.id, **member_doc.to_dict())

    today_str = py_date.today().strftime("%Y-%m-%d")
    reason_str = f"Attended event: {event.title}"

    if req.attended:
        # Mark as attended
        if req.user_id not in event.attended_users:
            event.attended_users.append(req.user_id)
            
            # Award Points
            member.points_history.append(PointAwardEntry(
                date=today_str,
                points=req.points,
                reason=reason_str,
                activity_type="event",
                awarded_by="Admin"
            ))
            
            # Activity Log
            existing = next((e for e in member.activity_log if e.date == today_str), None)
            if existing:
                existing.count += 1
            else:
                member.activity_log.append(ActivityEntry(date=today_str, count=1))
                
            member.points += req.points
            
            # Check Badges
            new_badges = check_and_award_badges(member)
            member.badges.extend(new_badges)
    else:
        # Unmark attendance
        if req.user_id in event.attended_users:
            event.attended_users.remove(req.user_id)
            
            # Reclaim Points
            matching_entry = next((e for e in member.points_history if e.reason == reason_str), None)
            if matching_entry:
                member.points -= matching_entry.points
                member.points_history.remove(matching_entry)
                if member.points < 0:
                    member.points = 0

    # Save Event and Member
    db.collection("events").document(event.id).set(event.model_dump(exclude={"id"}))
    db.collection("members").document(member.id).set(member.model_dump(exclude={"id"}))

    return {"status": "success", "attended": req.attended}
