from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.auth_schema import LoginRequest, TokenResponse
from backend.services.auth_service import authenticate_user


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, summary="Log in and receive a JWT")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return TokenResponse(access_token=authenticate_user(db, payload.username, payload.password))