from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.user_service.dependencies import get_current_user
from backend.user_service.models.user import User
from backend.user_service.schemas.user_schema import UserResponse
from backend.user_service.database import get_db

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=UserResponse, summary="Get the authenticated user")
def get_current_user_profile(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)

@router.get("/{user_id}/name", summary="Get full name and phone of a user")
def get_user_name(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"fullName": user.full_name, "phone": user.phone}