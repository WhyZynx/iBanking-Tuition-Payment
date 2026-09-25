from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.user_schema import UserResponse


router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=UserResponse, summary="Get the authenticated user")
def get_current_user_profile(user: User = Depends(get_current_user)) -> User:
    return user