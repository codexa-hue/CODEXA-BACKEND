from typing import List, Union, Optional
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated


def parse_cors(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        import json
        return json.loads(v) if isinstance(v, str) else v
    return []


class Settings(BaseSettings):
    PROJECT_NAME: str = "Coding Club API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days



    # CORS
    BACKEND_CORS_ORIGINS: Annotated[
        List[str], BeforeValidator(parse_cors)
    ] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "https://sitam-coding-club-fb39a.web.app",
        "https://sitam-coding-club-fb39a.firebaseapp.com",
        "https://sitamcodexa.org",
        "https://www.sitamcodexa.org",
        "https://codexa-frontend-git-main-sitam-codexa.vercel.app",
        "https://codexa-frontend.vercel.app",
        "https://codexa-coding-club.vercel.app",
        "https://codexa-frontend-coral.vercel.app",
    ]



    # Firebase Settings
    FIREBASE_PROJECT_ID: str = "sitam-coding-club-fb39a"
    FIREBASE_CREDENTIALS_PATH: Optional[str] = "firebase-credentials.json"
    FIREBASE_STORAGE_BUCKET: Optional[str] = None


    # SMTP Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "CODEXA Coding Club"
    SMTP_FROM_EMAIL: str = ""
    RESEND_API_KEY: Optional[str] = None
    BREVO_API_KEY: Optional[str] = None



    # Frontend base URL (used in password-reset links)
    FRONTEND_URL: str = "https://sitamcodexa.org"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Safe startup check to debug Render loading
if settings.RESEND_API_KEY:
    val = settings.RESEND_API_KEY.strip().strip("'").strip('"')
    masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "too_short"
    print(f"[STARTUP] Loaded RESEND_API_KEY: {masked} (length: {len(val)})")
else:
    print("[STARTUP] RESEND_API_KEY is NOT loaded on the server!")

