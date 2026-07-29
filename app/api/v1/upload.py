import os
import uuid
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from app.api.deps import get_current_active_user
from app.models.user import User
from app.core.config import settings

router = APIRouter()

# Configure Cloudinary
if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )
else:
    print("[WARNING] Cloudinary credentials are not configured! Uploads will fail.")

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
    
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Upload failed: Cloudinary is not configured on the server. Please check environment settings."
        )

    # Save the file to Cloudinary
    try:
        file.file.seek(0)
        upload_result = cloudinary.uploader.upload(
            file.file,
            resource_type="auto",
            folder="codexa"
        )
        public_url = upload_result.get("secure_url")
        filename = upload_result.get("public_id")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not upload file to storage: {str(e)}"
        )
        
    return {
        "url": public_url,
        "filename": filename,
        "type": "video" if file_ext in ALLOWED_VIDEO_EXTENSIONS else "image"
    }


