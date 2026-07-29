import os
import cloudinary
import cloudinary.uploader
from app.core.config import settings

# Configure Cloudinary globally
if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )
else:
    print("[WARNING] Cloudinary credentials are not configured! Operations will fail.")

def delete_cloudinary_file(url: str):
    """
    Given a Cloudinary secure/insecure URL, extract the public_id and delete it from Cloudinary storage.
    """
    if not url or "res.cloudinary.com" not in url:
        return
    try:
        # A cloudinary URL looks like: https://res.cloudinary.com/<cloud_name>/<resource_type>/upload/v[version]/<public_id>.<ext>
        # e.g., https://res.cloudinary.com/cb0kazcs/image/upload/v1722240000/codexa/abcde.jpg
        parts = url.split("/upload/")
        if len(parts) < 2:
            return
        
        # parts[1] is: v1722240000/codexa/abcde.jpg or similar
        sub_parts = parts[1].split("/", 1)
        if len(sub_parts) < 2:
            return
        
        # sub_parts[1] is: codexa/abcde.jpg
        path_without_ext = sub_parts[1].rsplit(".", 1)[0]
        
        # Determine resource_type (image or video) from URL
        resource_type = "image"
        if "/video/" in url:
            resource_type = "video"
        elif "/raw/" in url:
            resource_type = "raw"
            
        cloudinary.uploader.destroy(path_without_ext, resource_type=resource_type)
        print(f"[CLOUDINARY] Deleted file: {path_without_ext} ({resource_type})")
    except Exception as e:
        print(f"[CLOUDINARY] Error deleting file {url}: {e}")
