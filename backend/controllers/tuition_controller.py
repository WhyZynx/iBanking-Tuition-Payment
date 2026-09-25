from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models.tuition_model import TuitionBill
from backend.services.tuition_service import (
    get_all_tuitions,
    get_tuition,
    mark_tuition_as_paid
)


router = APIRouter(
    prefix="/api/v1/tuition",
    tags=["Tuition"]
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
    response_model=TuitionBill
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