from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import date
from app.api.deps import get_current_active_user, get_current_admin
from app.models.user import User
from app.models.member import Member, PointAwardEntry, ActivityEntry
from app.models.challenge import (
    Challenge, ChallengeCreate, ChallengeResponse,
    ChallengeSubmission, ChallengeSubmissionResponse, SubmissionStatusRequest
)
from app.api.v1.members import check_and_award_badges
from app.core.database import get_db

router = APIRouter()

# ── Student API Endpoints ──────────────────────────────────────────

@router.get("/", response_model=List[ChallengeResponse])
async def read_challenges(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user)
):
    """Get list of all published weekly challenges. Accessible by active students."""
    db = get_db()
    docs = db.collection("challenges").get()
    challenges = [Challenge(id=doc.id, **doc.to_dict()) for doc in docs]
    return challenges[offset : offset + limit]


@router.post("/{id}/submit", response_model=ChallengeSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_challenge(
    id: str,
    github_url: str,
    comments: str = "",
    current_user: User = Depends(get_current_active_user)
):
    """Submit a solution to a weekly challenge. Accessible by active students."""
    db = get_db()
    
    # Verify challenge exists
    chal_doc = db.collection("challenges").document(id).get()
    if not chal_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    challenge = Challenge(id=chal_doc.id, **chal_doc.to_dict())
    
    # Get student name
    member_docs = db.collection("members").where("user_id", "==", current_user.id).limit(1).get()
    if not member_docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member profile not found")
    member = Member(id=member_docs[0].id, **member_docs[0].to_dict())
    
    # Create submission record
    sub = ChallengeSubmission(
        challenge_id=id,
        challenge_title=challenge.title,
        user_id=current_user.id,
        student_name=member.name,
        github_url=github_url,
        comments=comments,
        status="Pending"
    )
    
    doc_ref = db.collection("challenge_submissions").document()
    doc_ref.set(sub.model_dump(exclude={"id"}))
    sub.id = doc_ref.id
    
    return sub


@router.get("/submissions/my", response_model=List[ChallengeSubmissionResponse])
async def read_my_submissions(
    current_user: User = Depends(get_current_active_user)
):
    """Get all submissions for the currently authenticated member."""
    db = get_db()
    docs = db.collection("challenge_submissions").where("user_id", "==", current_user.id).get()
    return [ChallengeSubmission(id=doc.id, **doc.to_dict()) for doc in docs]


# ── Admin API Endpoints ───────────────────────────────────────────

@router.post("/", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    chal_in: ChallengeCreate,
    current_user: User = Depends(get_current_admin)
):
    """Publish a new weekly challenge. Restricted to Admins."""
    db = get_db()
    challenge = Challenge(**chal_in.model_dump())
    
    doc_ref = db.collection("challenges").document()
    doc_ref.set(challenge.model_dump(exclude={"id"}))
    challenge.id = doc_ref.id
    
    return challenge


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_challenge(
    id: str,
    current_user: User = Depends(get_current_admin)
):
    """Delete a weekly challenge and its solutions. Restricted to Admins."""
    db = get_db()
    
    # Delete challenge doc
    db.collection("challenges").document(id).delete()
    
    # Cleanup matching submissions
    sub_docs = db.collection("challenge_submissions").where("challenge_id", "==", id).get()
    for doc in sub_docs:
        db.collection("challenge_submissions").document(doc.id).delete()
        
    return None


@router.get("/{id}/submissions", response_model=List[ChallengeSubmissionResponse])
async def read_challenge_submissions(
    id: str,
    current_user: User = Depends(get_current_admin)
):
    """Get all submissions for a specific challenge. Restricted to Admins."""
    db = get_db()
    docs = db.collection("challenge_submissions").where("challenge_id", "==", id).get()
    return [ChallengeSubmission(id=doc.id, **doc.to_dict()) for doc in docs]


@router.get("/submissions/all", response_model=List[ChallengeSubmissionResponse])
async def read_all_submissions(
    current_user: User = Depends(get_current_admin)
):
    """Get all submissions across all challenges. Restricted to Admins."""
    db = get_db()
    docs = db.collection("challenge_submissions").get()
    return [ChallengeSubmission(id=doc.id, **doc.to_dict()) for doc in docs]


@router.put("/submissions/{submission_id}/status", response_model=ChallengeSubmissionResponse)
async def update_submission_status(
    submission_id: str,
    req: SubmissionStatusRequest,
    current_user: User = Depends(get_current_admin)
):
    """Approve or Reject a student solution. If approved, automatically awards leaderboard points."""
    db = get_db()
    
    # Fetch submission
    sub_doc = db.collection("challenge_submissions").document(submission_id).get()
    if not sub_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    submission = ChallengeSubmission(id=sub_doc.id, **sub_doc.to_dict())
    
    # If state hasn't changed, return
    if submission.status == req.status:
        return submission
        
    # Fetch challenge info
    chal_doc = db.collection("challenges").document(submission.challenge_id).get()
    if not chal_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge context lost")
    challenge = Challenge(id=chal_doc.id, **chal_doc.to_dict())
    
    # Fetch member profile
    member_docs = db.collection("members").where("user_id", "==", submission.user_id).limit(1).get()
    if not member_docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member profile not found")
    member_doc = member_docs[0]
    member = Member(id=member_doc.id, **member_doc.to_dict())
    
    today_str = date.today().strftime("%Y-%m-%d")
    reason_str = f"Solved Challenge: {challenge.title}"
    
    # Execute status transitions
    if req.status == "Approved":
        # Check if already approved to prevent double points
        already_rewarded = any(e.reason == reason_str for e in member.points_history)
        if not already_rewarded:
            # Award points
            member.points_history.append(PointAwardEntry(
                date=today_str,
                points=challenge.points,
                reason=reason_str,
                activity_type="general",
                awarded_by="Admin"
            ))
            
            # Update activity log
            existing = next((e for e in member.activity_log if e.date == today_str), None)
            if existing:
                existing.count += 1
            else:
                member.activity_log.append(ActivityEntry(date=today_str, count=1))
                
            member.points += challenge.points
            
            # Award badges if rules apply
            new_badges = check_and_award_badges(member)
            member.badges.extend(new_badges)
            
    elif req.status == "Rejected":
        # If transitioning from Approved to Rejected, reclaim points
        if submission.status == "Approved":
            matching_entry = next((e for e in member.points_history if e.reason == reason_str), None)
            if matching_entry:
                member.points -= matching_entry.points
                member.points_history.remove(matching_entry)
                if member.points < 0:
                    member.points = 0
                    
    # Write back updates
    submission.status = req.status
    submission.feedback = req.feedback
    db.collection("challenge_submissions").document(submission.id).set(submission.model_dump(exclude={"id"}))
    db.collection("members").document(member.id).set(member.model_dump(exclude={"id"}))
    
    return submission
