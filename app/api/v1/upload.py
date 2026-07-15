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
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save the file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {str(e)}"
        )
        
    # Return relative URL
    return {
        "url": f"/uploads/{unique_filename}",
        "filename": unique_filename,
        "type": "video" if file_ext in ALLOWED_VIDEO_EXTENSIONS else "image"
    }
