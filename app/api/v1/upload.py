import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

# Directory to save files
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload an image or video file. Accessible by active members.
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS and file_ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only images and videos are allowed."
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    
    # Save the file to Firebase Storage
    try:
        from firebase_admin import storage
        bucket = storage.bucket()
        blob = bucket.blob(f"uploads/{unique_filename}")
        file.file.seek(0)
        blob.upload_from_file(file.file, content_type=file.content_type)
        
        try:
            blob.make_public()
            public_url = blob.public_url
        except Exception:
            # Fallback to standard Firebase Storage HTTP URL
            public_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/uploads%2F{unique_filename}?alt=media"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not upload file to storage: {str(e)}"
        )
        
    # Return Firebase Storage URL
    return {
        "url": public_url,
        "filename": unique_filename,
        "type": "video" if file_ext in ALLOWED_VIDEO_EXTENSIONS else "image"
    }

