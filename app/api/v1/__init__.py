from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.members import router as members_router
from app.api.v1.events import router as events_router
from app.api.v1.announcements import router as announcements_router
from app.api.v1.projects import router as projects_router
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.resources import router as resources_router
from app.api.v1.join_requests import router as join_requests_router
from app.api.v1.upload import router as upload_router
from app.api.v1.challenges import router as challenges_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(members_router, prefix="/members", tags=["Members Profile"])
api_router.include_router(events_router, prefix="/events", tags=["Events & Workshops"])
api_router.include_router(announcements_router, prefix="/announcements", tags=["Announcements"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects Showcase"])
api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["Leaderboard Rankings"])
api_router.include_router(resources_router, prefix="/resources", tags=["Study Resources"])
api_router.include_router(join_requests_router, prefix="/join_requests", tags=["Join Requests Application"])
api_router.include_router(upload_router, prefix="/upload", tags=["File Uploads"])
api_router.include_router(challenges_router, prefix="/challenges", tags=["Weekly Challenges"])
