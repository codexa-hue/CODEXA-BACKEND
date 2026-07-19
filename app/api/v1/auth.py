import random
import string
from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.email import send_password_reset_otp
from app.models.user import User, Token
from app.models.member import Member
from app.models.password_reset import PasswordResetOTP, ForgotPasswordRequest, VerifyOTPRequest
from app.core.database import get_db

router = APIRouter()


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


# ── Login ─────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login for both admins and approved members. Returns a JWT token."""
    db = get_db()
    users_ref = db.collection("users")
    docs = users_ref.where("email", "==", form_data.username).limit(1).get()
    if not docs:
        docs = users_ref.where("unique_id", "==", form_data.username).limit(1).get()
    user_doc = docs[0] if docs else None
    
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect ID, email or password",
        )
        
    user = User(id=user_doc.id, **user_doc.to_dict())
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect ID, email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact the admin.",
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=create_access_token(
            subject=str(user.id),
            expires_delta=access_token_expires,
            role=user.role,
        )
    )


# ── Forgot Password — send OTP ────────────────────────────────────

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(body: ForgotPasswordRequest):
    """
    Send a 6-digit OTP to the user's email for password reset.
    Always returns 200 (even if email not found) to avoid user enumeration.
    """
    db = get_db()
    users_ref = db.collection("users")
    docs = users_ref.where("email", "==", body.email).limit(1).get()
    user_doc = docs[0] if docs else None
    
    if not user_doc:
        # Return OK to avoid revealing whether the email exists
        return {"message": "If this email is registered, an OTP has been sent."}

    user = User(id=user_doc.id, **user_doc.to_dict())

    # Delete any previous OTPs for this email to save database space
    otps_ref = db.collection("password_reset_otps")
    old_docs = otps_ref.where("email", "==", str(body.email)).get()
    for doc in old_docs:
        otps_ref.document(doc.id).delete()


    # Generate and store new OTP
    otp = _generate_otp()
    reset_record = PasswordResetOTP(email=str(body.email), otp=otp)
    
    doc_ref = otps_ref.document()
    doc_ref.set(reset_record.model_dump(exclude={"id"}))

    # Resolve the user's name from their member profile
    members_ref = db.collection("members")
    member_docs = members_ref.where("user_id", "==", str(user.id)).limit(1).get()
    member_doc = member_docs[0] if member_docs else None
    
    name = member_doc.to_dict().get("name") if member_doc else str(body.email).split("@")[0].capitalize()

    # Send OTP email (non-blocking — errors are logged, not raised)
    send_password_reset_otp(
        to_email=str(body.email),
        name=name,
        otp=otp,
        frontend_url=settings.FRONTEND_URL,
    )

    return {"message": "If this email is registered, an OTP has been sent."}


# ── Reset Password — verify OTP + set new password ────────────────

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: VerifyOTPRequest):
    """
    Verify the OTP and update the user's password.
    The OTP must be unused and not expired (15-minute window).
    """
    db = get_db()
    otps_ref = db.collection("password_reset_otps")
    otp_docs = otps_ref.where("email", "==", str(body.email))\
                       .where("otp", "==", body.otp)\
                       .where("used", "==", False)\
                       .get()
                       
    valid_otps = [PasswordResetOTP(id=doc.id, **doc.to_dict()) for doc in otp_docs]
    valid_otps.sort(key=lambda x: x.created_at, reverse=True)
    record = valid_otps[0] if valid_otps else None

    if not record or not record.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    # Find the user
    users_ref = db.collection("users")
    docs = users_ref.where("email", "==", body.email).limit(1).get()
    user_doc = docs[0] if docs else None
    
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user = User(id=user_doc.id, **user_doc.to_dict())

    users_ref.document(user.id).update({"hashed_password": get_password_hash(body.new_password)})

    # Delete the used OTP from Firestore to save space
    otps_ref.document(record.id).delete()

    return {"message": "Password updated successfully. You can now sign in."}



from pydantic import BaseModel, Field
from app.api.deps import get_current_active_user

class CheckOTPRequest(BaseModel):
    email: str
    otp: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(body: CheckOTPRequest):
    """
    Verify if the OTP matches and is still valid. Does not mark it as used yet.
    """
    db = get_db()
    otps_ref = db.collection("password_reset_otps")
    otp_docs = otps_ref.where("email", "==", str(body.email))\
                       .where("otp", "==", body.otp)\
                       .where("used", "==", False)\
                       .get()
                       
    valid_otps = [PasswordResetOTP(id=doc.id, **doc.to_dict()) for doc in otp_docs]
    valid_otps.sort(key=lambda x: x.created_at, reverse=True)
    record = valid_otps[0] if valid_otps else None
    
    if not record or not record.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one."
        )
    return {"message": "OTP is valid."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Change the authenticated user's password.
    Requires the current password for verification.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    db = get_db()
    db.collection("users").document(current_user.id).update({
        "hashed_password": get_password_hash(body.new_password)
    })

    return {"message": "Password changed successfully."}


# ── Get current admin profile ─────────────────────────────────────

@router.get("/me", status_code=status.HTTP_200_OK)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Return the current authenticated user's public profile."""
    db = get_db()
    doc = db.collection("users").document(current_user.id).get()
    data = doc.to_dict() if doc.exists else {}
    return {
        "id": current_user.id,
        "email": str(current_user.email),
        "role": current_user.role,
        "display_name": data.get("display_name", ""),
        "unique_id": current_user.unique_id or data.get("unique_id", ""),
    }


# ── Update admin display name ─────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=60)

@router.patch("/me", status_code=status.HTTP_200_OK)
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Update the authenticated user's display name."""
    db = get_db()
    db.collection("users").document(current_user.id).update({
        "display_name": body.display_name.strip()
    })
    return {"message": "Profile updated.", "display_name": body.display_name.strip()}


# ── Refresh Token ──────────────────────────────────────────────────

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: User = Depends(get_current_active_user)):
    """
    Generate a new access token for the currently authenticated user to extend their session.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=create_access_token(
            subject=str(current_user.id),
            expires_delta=access_token_expires,
            role=current_user.role,
        )
    )
