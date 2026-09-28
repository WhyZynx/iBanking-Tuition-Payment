from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.user_service.models.user import User
from backend.user_service.security import create_access_token, verify_password


def authenticate_user(db: Session, username: str, password: str) -> str:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return create_access_token(user.user_id, user.username)
