import hmac

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.tuition_service.config import INTERNAL_API_KEY
from backend.tuition_service.models.tuition_model import TuitionBill
from backend.tuition_service.services.tuition_service import (
    get_all_tuitions,
    get_tuition,
    claim_tuition_payment,
    mark_tuition_as_paid,
    release_tuition_payment_claim,
)


router = APIRouter(
    prefix="/api/v1/tuition",
    tags=["Tuition"]
)


class TuitionPaymentClaimRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=36)


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
    response_model=list[TuitionBill]
)
def find_all_tuitions() -> list[TuitionBill]:
    return get_all_tuitions()

@router.get(
    "/{student_id}",
    response_model=TuitionBill
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


@router.put(
    "/{student_id}/pay",
    response_model=TuitionBill,
    dependencies=[Depends(require_internal_api_key)]
)
def pay_tuition(student_id: str) -> TuitionBill:
    return mark_tuition_as_paid(student_id)


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


@app.get("/health")
def health_check():
    return {
        "service": "tuition-service",
        "status": "UP"
    }
