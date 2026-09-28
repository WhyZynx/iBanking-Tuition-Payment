import hmac

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.tuition_service.config import INTERNAL_API_KEY
from backend.tuition_service.models.tuition_model import TuitionBill
from backend.tuition_service.services.tuition_service import (
    get_all_tuitions,
    get_tuition,
    mark_tuition_as_paid
)


router = APIRouter(
    prefix="/api/v1/tuition",
    tags=["Tuition"]
)


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
def find_all_tuitions():
    return get_all_tuitions()

@router.get(
    "/{student_id}",
    response_model=TuitionBill
)
def find_tuition(student_id: str):
    return get_tuition(student_id)


@router.put(
    "/{student_id}/pay",
    response_model=TuitionBill,
    dependencies=[Depends(require_internal_api_key)]
)
def pay_tuition(student_id: str):
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
