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

    # Frontend base URL (used in password-reset links)
    FRONTEND_URL: str = "https://sitamcodexa.org"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
