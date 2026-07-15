from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from app.api.deps import get_current_admin
from app.models.user import User, UserRole
from app.models.member import Member, SocialLinks
from app.models.join_request import (
    JoinRequest,
    JoinRequestCreate,
    JoinRequestUpdateStatus,
    JoinRequestResponse,
    RequestStatus,
)
from app.core.security import get_password_hash
from app.core.email import (
    send_application_received,
    send_application_approved,
    send_application_rejected,
)
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


class BulkApprovalResponse(BaseModel):
    approved_count: int
    skipped_count: int
    message: str


def generate_unique_member_id(joining_year: int, db) -> str:
    year_suffix = str(joining_year)[-2:]
    prefix = f"{year_suffix}CDX"
    
    # Query all users with this prefix in their unique_id
    docs = db.collection("users")\
        .where(field_path="unique_id", op_string=">=", value=prefix)\
        .where(field_path="unique_id", op_string="<", value=prefix + "\uf8ff")\
        .get()
        
    existing_nums = []
    for doc in docs:
        val = doc.to_dict().get("unique_id")
        if val and val.startswith(prefix):
            suffix_str = val[len(prefix):]
            try:
                num = int(suffix_str)
                existing_nums.append(num)
            except ValueError:
                pass
                
    next_num = max(existing_nums) + 1 if existing_nums else 1
    
    while True:
        formatted_num = f"{next_num:02d}"
        unique_id = f"{prefix}{formatted_num}"
        # Double check uniqueness in users collection just in case
        existing = db.collection("users").where(field_path="unique_id", op_string="==", value=unique_id).limit(1).get()
        if not existing:
            return unique_id
        next_num += 1


# ── PUBLIC: submit a registration request ────────────────────────

@router.post("/", response_model=JoinRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_join_request(request_in: JoinRequestCreate):
    """
    Submit a membership application.
    The account is NOT created yet — it is pending admin approval.
    """
    db = get_db()
    join_docs = db.collection("join_requests").where("email", "==", request_in.email).limit(1).get()
    existing_doc = join_docs[0] if join_docs else None
    existing = JoinRequest(id=existing_doc.id, **existing_doc.to_dict()) if existing_doc else None
    
    if existing:
        if existing.status == RequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An application with this email is already pending review.",
            )
        if existing.status == RequestStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A previous application for this email was rejected. Contact the admin.",
            )
        if existing.status == RequestStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email already has an approved account. Please sign in.",
            )

    # Block if an account already exists
    users_docs = db.collection("users").where("email", "==", request_in.email).limit(1).get()
    user_doc = users_docs[0] if users_docs else None
    existing_user = User(id=user_doc.id, **user_doc.to_dict()) if user_doc else None
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already registered. Please sign in.",
        )

    # Hash password before storing — never store plain text
    hashed_pw = get_password_hash(request_in.password)

    request = JoinRequest(
        name=request_in.name,
        email=request_in.email,
        year=request_in.year,
        joining_year=request_in.joining_year,
        skills=request_in.skills or [],
        reason_to_join=request_in.reason_to_join,
        hashed_password=hashed_pw,
    )
    
    doc_ref = db.collection("join_requests").document()
    doc_ref.set(request.model_dump(exclude={"id"}))
    request.id = doc_ref.id

    # Send confirmation email to the applicant
    send_application_received(to_email=str(request_in.email), name=request_in.name)

    return request


# ── ADMIN: list all requests ──────────────────────────────────────

@router.get("/", response_model=List[JoinRequestResponse])
async def read_join_requests(
    status_filter: Optional[RequestStatus] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_admin),
):
    db = get_db()
    ref = db.collection("join_requests")
    if status_filter:
        docs = ref.where("status", "==", status_filter).get()
    else:
        docs = ref.get()
        
    requests = [JoinRequest(id=doc.id, **doc.to_dict()) for doc in docs]
    return requests[offset : offset + limit]


# ── ADMIN: get one request ────────────────────────────────────────

@router.get("/{id}", response_model=JoinRequestResponse)
async def read_join_request(id: str, current_user: User = Depends(get_current_admin)):
    db = get_db()
    doc = db.collection("join_requests").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return JoinRequest(id=doc.id, **doc.to_dict())


# ── ADMIN: approve or reject ──────────────────────────────────────

@router.put("/{id}/status", response_model=JoinRequestResponse)
async def update_request_status(
    id: str,
    status_in: JoinRequestUpdateStatus,
    current_user: User = Depends(get_current_admin),
):
    """
    Approve or reject a membership application.

    On APPROVED:
      - Creates a User account using the password the applicant chose.
      - Creates a Member profile with their submitted details.
      - The applicant can now log in with their original email + password.
    """
    db = get_db()
    doc = db.collection("join_requests").document(id).get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        
    request = JoinRequest(id=doc.id, **doc.to_dict())

    if request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application already processed: {request.status}",
        )

    if status_in.status == RequestStatus.APPROVED:
        member_count = len(db.collection("members").get())
        if member_count >= 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approval limit reached: The club is capped at a maximum of 15 members."
            )

    request.status = status_in.status
    db.collection("join_requests").document(request.id).set(request.model_dump(exclude={"id"}))

    # ── Auto-provision account on approval ──────────────────────
    if request.status == RequestStatus.APPROVED:
        users_docs = db.collection("users").where("email", "==", request.email).limit(1).get()
        user_doc = users_docs[0] if users_docs else None
        existing_user = User(id=user_doc.id, **user_doc.to_dict()) if user_doc else None
        
        unique_id = None
        if not existing_user:
            # Generate unique member ID
            unique_id = generate_unique_member_id(request.joining_year, db)
            
            # Use hashed password saved at submission time.
            # Legacy records (created before password field) get a temp password.
            if request.hashed_password:
                hashed_pw = request.hashed_password
            else:
                # Fallback for old records — generate temp password
                temp_plain = f"{request.email.split('@')[0].capitalize()}@Club2026"
                hashed_pw = get_password_hash(temp_plain)
                print(f"[LEGACY ONBOARDING] No stored password for {request.email}. Temp password: {temp_plain}")

            user = User(
                email=request.email,
                hashed_password=hashed_pw,
                role=UserRole.MEMBER,
                is_active=True,
                unique_id=unique_id,
            )
            user_doc_ref = db.collection("users").document()
            user_doc_ref.set(user.model_dump(exclude={"id"}))
            user.id = user_doc_ref.id

            member = Member(
                user_id=str(user.id),
                name=request.name,
                role="Member",
                year=request.year,
                skills=request.skills,
                socials=SocialLinks(),
                points=10,
            )
            member_doc_ref = db.collection("members").document()
            member_doc_ref.set(member.model_dump(exclude={"id"}))
            member.id = member_doc_ref.id

            print(f"[ONBOARDING] Account created for {request.email} with Unique ID {unique_id}")
        else:
            unique_id = existing_user.unique_id or "Already Onboarded"

        # Send approval email
        send_application_approved(
            to_email=str(request.email),
            name=request.name,
            unique_id=unique_id,
            frontend_url=settings.FRONTEND_URL,
        )

    elif request.status == RequestStatus.REJECTED:
        # Send rejection email
        send_application_rejected(to_email=str(request.email), name=request.name)

    return request


# ── ADMIN: approve all pending requests ──────────────────────────────────────

@router.post("/approve-all", response_model=BulkApprovalResponse)
async def approve_all_pending(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
):
    """
    Approve every pending membership application in one shot,
    up to the club cap of 15 members.
    """
    db = get_db()

    # Current member count
    current_member_count = len(db.collection("members").get())
    available_slots = 15 - current_member_count

    if available_slots <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval limit reached: The club is capped at a maximum of 15 members.",
        )

    # All pending requests
    pending_docs = db.collection("join_requests").where("status", "==", RequestStatus.PENDING).get()
    pending_requests = [JoinRequest(id=doc.id, **doc.to_dict()) for doc in pending_docs]

    approved_count = 0
    skipped_count = 0

    for request in pending_requests:
        if approved_count >= available_slots:
            skipped_count += 1
            continue

        # Mark as approved
        request.status = RequestStatus.APPROVED
        db.collection("join_requests").document(request.id).set(request.model_dump(exclude={"id"}))

        # Check if user already exists
        users_docs = db.collection("users").where("email", "==", request.email).limit(1).get()
        user_doc = users_docs[0] if users_docs else None
        existing_user = User(id=user_doc.id, **user_doc.to_dict()) if user_doc else None

        unique_id = None
        if not existing_user:
            unique_id = generate_unique_member_id(request.joining_year, db)

            if request.hashed_password:
                hashed_pw = request.hashed_password
            else:
                temp_plain = f"{request.email.split('@')[0].capitalize()}@Club2026"
                hashed_pw = get_password_hash(temp_plain)
                print(f"[LEGACY BULK] No stored password for {request.email}. Temp: {temp_plain}")

            user = User(
                email=request.email,
                hashed_password=hashed_pw,
                role=UserRole.MEMBER,
                is_active=True,
                unique_id=unique_id,
            )
            user_doc_ref = db.collection("users").document()
            user_doc_ref.set(user.model_dump(exclude={"id"}))
            user.id = user_doc_ref.id

            member = Member(
                user_id=str(user.id),
                name=request.name,
                role="Member",
                year=request.year,
                skills=request.skills,
                socials=SocialLinks(),
                points=10,
            )
            member_doc_ref = db.collection("members").document()
            member_doc_ref.set(member.model_dump(exclude={"id"}))
            member.id = member_doc_ref.id

            print(f"[BULK ONBOARDING] Account created for {request.email} with ID {unique_id}")
        else:
            unique_id = existing_user.unique_id or "Already Onboarded"

        # Fire approval email in background so it doesn't block the loop
        background_tasks.add_task(
            send_application_approved,
            to_email=str(request.email),
            name=request.name,
            unique_id=unique_id,
            frontend_url=settings.FRONTEND_URL,
        )

        approved_count += 1

    parts = [f"Successfully approved {approved_count} application(s)."]
    if skipped_count > 0:
        parts.append(f"{skipped_count} skipped — club cap of 15 members reached.")
    message = " ".join(parts)

    return BulkApprovalResponse(
        approved_count=approved_count,
        skipped_count=skipped_count,
        message=message,
    )
