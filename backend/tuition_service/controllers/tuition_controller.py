import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from backend.tuition_service.config import (
    INTERNAL_API_KEY,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)
from backend.tuition_service.models.tuition_model import TuitionBill
from backend.tuition_service.services.tuition_service import (
    get_all_tuitions,
    get_tuition,
    claim_tuition_payment,
    mark_tuition_as_paid,
    release_tuition_payment_claim,
    get_tuition_payment_claim_status,
)


router = APIRouter(
    prefix="/api/v1/tuition",
    tags=["Tuition"]
)


class TuitionPaymentClaimRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=36)


bearer_scheme = HTTPBearer(auto_error=False)


def require_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> int:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not JWT_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT authentication is not configured",
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject.isdecimal():
            raise JWTError("Invalid subject")
        return int(subject)
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_tuition_reader(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    x_internal_api_key: str | None = Header(default=None),
) -> int | None:
    if x_internal_api_key and INTERNAL_API_KEY and hmac.compare_digest(
        x_internal_api_key,
        INTERNAL_API_KEY,
    ):
        return None
    return require_authenticated_user(credentials)


def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None)
):
    if not INTERNAL_API_KEY or not hmac.compare_digest(
        x_internal_api_key or "",
        INTERNAL_API_KEY
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing internal API key"
        )


@router.get(
    "",
    response_model=list[TuitionBill],
    dependencies=[Depends(require_tuition_reader)],
)
def find_all_tuitions() -> list[TuitionBill]:
    return get_all_tuitions()

@router.get(
    "/{student_id}",
    response_model=TuitionBill,
    dependencies=[Depends(require_tuition_reader)],
)
def find_tuition(student_id: str) -> TuitionBill:
    return get_tuition(student_id)


@router.post(
    "/{student_id}/claim",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_api_key)],
)
def claim_payment(student_id: str, payload: TuitionPaymentClaimRequest):
    return claim_tuition_payment(student_id, payload.transaction_id)


@router.delete(
    "/{student_id}/claim/{transaction_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_api_key)],
)
def release_claim(student_id: str, transaction_id: str):
    return release_tuition_payment_claim(student_id, transaction_id)


@router.get(
    "/{student_id}/claim/{transaction_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_api_key)],
)
def get_claim_status(student_id: str, transaction_id: str):
    return get_tuition_payment_claim_status(student_id, transaction_id)


@router.put(
    "/{student_id}/pay",
    response_model=TuitionBill,
    dependencies=[Depends(require_internal_api_key)]
)
def pay_tuition(
    student_id: str,
    payload: TuitionPaymentClaimRequest | None = None,
) -> TuitionBill:
    transaction_id = payload.transaction_id if payload is not None else None
    return mark_tuition_as_paid(student_id, transaction_id)


app = FastAPI(
    title="iBanking Tuition Service",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(router)
