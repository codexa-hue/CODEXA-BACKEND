from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.announcement import Announcement, AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.core.database import get_db
from app.core.email import send_announcement_deleted_notification

router = APIRouter()

def _is_expired(ann: Announcement) -> bool:
    """Return True if the announcement has passed its expiry date."""
    if ann.expires_at is None:
        return False
    expires = ann.expires_at
    now = datetime.now(timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return now > expires


@router.get("/", response_model=List[AnnouncementResponse])
async def read_announcements(limit: int = 100, offset: int = 0):
    """
    Get all non-expired announcements. Accessible by anyone.
    Announcements whose expires_at is in the past are silently excluded.
    """
    db = get_db()
    docs = db.collection("announcements").get()
    all_ann = [Announcement(id=doc.id, **doc.to_dict()) for doc in docs]
    
    def get_ann_created_at(a):
        c = a.created_at
        if c.tzinfo is None:
            c = c.replace(tzinfo=timezone.utc)
        return c
        
    all_ann.sort(key=get_ann_created_at, reverse=True)
    all_ann = all_ann[offset : offset + limit]
    
    return [a for a in all_ann if not _is_expired(a)]


@router.get("/admin/all", response_model=List[AnnouncementResponse])
async def read_all_announcements_admin(
    current_user: User = Depends(get_current_admin),
    limit: int = 100,
    offset: int = 0,
):
    """
    Get ALL announcements including expired ones. Admin only.
    Used in admin portal to allow manual deletion of expired items.
    """
    db = get_db()
    docs = db.collection("announcements").get()
    all_ann = [Announcement(id=doc.id, **doc.to_dict()) for doc in docs]
    
    def get_ann_created_at(a):
        c = a.created_at
        if c.tzinfo is None:
            c = c.replace(tzinfo=timezone.utc)
        return c
        
    all_ann.sort(key=get_ann_created_at, reverse=True)
    return all_ann[offset : offset + limit]


@router.get("/{id}", response_model=AnnouncementResponse)
async def read_announcement(id: str):
    """
    Get specific announcement details.
    """
    db = get_db()
    doc = db.collection("announcements").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
    return Announcement(id=doc.id, **doc.to_dict())


@router.post("/", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    announcement_in: AnnouncementCreate,
    current_user: User = Depends(get_current_admin)
):
    """
    Create a new announcement. Restricted to Admins.
    """
    db = get_db()
    announcement = Announcement(**announcement_in.model_dump())
    
    doc_ref = db.collection("announcements").document()
    doc_ref.set(announcement.model_dump(exclude={"id"}))
    announcement.id = doc_ref.id
    
    return announcement


@router.put("/{id}", response_model=AnnouncementResponse)
async def update_announcement(
    id: str,
    announcement_in: AnnouncementUpdate,
    current_user: User = Depends(get_current_admin)
):
    """
    Update an announcement. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("announcements").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
        
    announcement = Announcement(id=doc.id, **doc.to_dict())
    update_data = announcement_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(announcement, field, value)
        
    db.collection("announcements").document(announcement.id).set(announcement.model_dump(exclude={"id"}))
    return announcement


@router.delete("/expired", status_code=status.HTTP_200_OK)
async def delete_expired_announcements(
    current_user: User = Depends(get_current_admin)
):
    """
    Permanently delete all expired announcements. Admin only.
    """
    db = get_db()
    docs = db.collection("announcements").get()
    all_ann = [Announcement(id=doc.id, **doc.to_dict()) for doc in docs]
    expired = [a for a in all_ann if _is_expired(a)]
    for a in expired:
        db.collection("announcements").document(a.id).delete()
    return {"deleted": len(expired), "message": f"Removed {len(expired)} expired announcement(s)."}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin)
):
    """
    Delete a specific announcement. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("announcements").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
    announcement = Announcement(id=doc.id, **doc.to_dict())
    
    # 1. Check if the announcement was deleted before its expiry time
    if not _is_expired(announcement):
        # Fetch active users and member names
        users_docs = db.collection("users").where("is_active", "==", True).get()
        users_list = [User(id=ud.id, **ud.to_dict()) for ud in users_docs]
        
        members_docs = db.collection("members").get()
        members_map = {
            str(m.to_dict().get("user_id")): m.to_dict().get("name") 
            for m in members_docs if m.to_dict().get("user_id")
        }
        
        # Dispatch emails in the background
        for user in users_list:
            name = members_map.get(str(user.id)) or user.email.split("@")[0].capitalize()
            background_tasks.add_task(
                send_announcement_deleted_notification,
                user.email,
                name,
                announcement.title
            )
            
    # 2. Delete the announcement document
    db.collection("announcements").document(id).delete()
    return None
