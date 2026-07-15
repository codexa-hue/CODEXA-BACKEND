import asyncio
import os
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import api_router
from app.models.event import Event

async def delete_expired_events():
    from google.cloud.firestore_v1.base_query import FieldFilter
    while True:
        try:
            from app.core.database import get_db
            db = get_db()
            now = datetime.utcnow()
            # Fetch and delete events whose date has passed
            events_ref = db.collection("events")
            docs = events_ref.where(filter=FieldFilter("date", "<", now)).get()
            deleted_count = 0
            for doc in docs:
                events_ref.document(doc.id).delete()
                deleted_count += 1
            if deleted_count > 0:
                print(f"INFO:     Deleted {deleted_count} expired events automatically.")
        except Exception as e:
            print(f"ERROR:    Failed to delete expired events: {e}")
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Firebase Admin SDK and Firestore client
    await init_db()
    
    # Start background cleanup task
    bg_task = asyncio.create_task(delete_expired_events())
    
    yield
    
    # Shutdown:
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass
    print("INFO:     Firebase connection closed.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Serve uploads directory as static files
uploads_dir = os.path.join(os.getcwd(), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include core routes
app.include_router(api_router, prefix=settings.API_V1_STR)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Resolve absolute path to frontend dist directory
frontend_dist_path = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist")
)
assets_path = os.path.join(frontend_dist_path, "assets")

# Serve frontend build assets static directory if it exists
if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

# Catch-all route to serve the SPA index.html for frontend routing
@app.get("/{catchall:path}", tags=["Frontend"])
def serve_frontend(catchall: str):
    # If the request matches API path but is not found in routing, return 404
    api_prefix = settings.API_V1_STR.lstrip("/")
    if catchall.startswith(api_prefix) or catchall.startswith("docs") or catchall.startswith("openapi.json"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")

    index_file = os.path.join(frontend_dist_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "message": "Backend is running. Build the frontend (`npm run build` in frontend/) to serve the full UI.",
        "docs_url": "/docs"
    }

