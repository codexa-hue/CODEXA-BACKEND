from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
# pyright: ignore[reportMissingImports]
import jwt
# pyrefly: ignore [missing-import]
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import ALGORITHM
from app.models.user import User, TokenData, UserRole

# Configures OAuth2 token scheme; point it to the login route
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except (InvalidTokenError, ValidationError):
        raise credentials_exception
        
    from app.core.database import get_db
    db = get_db()
    user_doc = db.collection("users").document(token_data.user_id).get()
    if not user_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user = User(id=user_doc.id, **user_doc.to_dict())
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user

async def get_current_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    return current_user
