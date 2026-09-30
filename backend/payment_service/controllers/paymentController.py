import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.payment_service.config import JWT_ALGORITHM, JWT_SECRET_KEY
from backend.payment_service.database import get_db
from backend.payment_service.models.transactionModel import TransactionModel
from backend.payment_service.services.paymentService import PaymentService


router = APIRouter()
payment_service = PaymentService()
bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class ConfirmPaymentRequest(BaseModel):
    transactionId: str
    otpCode: str


class CreatePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str = Field(min_length=1, max_length=20)
    account_number: str = Field(min_length=1, max_length=20)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_pending_user_transaction(db_session, transaction_id, current_user_id):
    transaction = TransactionModel.find_by_id(db_session, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.payer_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transaction does not belong to the authenticated user",
        )
    if transaction.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction is not pending",
        )
    return transaction


@router.post("/api/v1/payments", status_code=status.HTTP_201_CREATED)
def create_payment(
    request: CreatePaymentRequest,
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    TransactionModel.fail_expired_pending(db_session)

    return payment_service.create_payment(
        db_session=db_session,
        payer_user_id=current_user_id,
        student_id=request.student_id,
        account_number=request.account_number,
    )


@router.post("/api/v1/payments/{transaction_id}/otp")
def request_otp(
    transaction_id: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    get_pending_user_transaction(db_session, transaction_id, current_user_id)
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(
        "OTP request validated for owned pending transaction %s and user %s",
        transaction_id,
        current_user_id,
    )
    return payment_service.request_otp(
        db_session=db_session,
        transaction_id=transaction_id,
        access_token=credentials.credentials,
    )


@router.post("/api/v1/payments/confirm")
def confirm_payment(
    request: ConfirmPaymentRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    return payment_service.confirm_payment(
        db_session=db_session,
        transaction_id=request.transactionId,
        otp_code=request.otpCode,
        payer_user_id=current_user_id,
        access_token=credentials.credentials,
    )


@router.post("/api/v1/payments/cancel-pending")
def cancel_pending_payments(
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    count = TransactionModel.fail_pending_by_user_id(
        db_session,
        current_user_id,
    )

    return {
        "message": "Pending transactions cancelled",
        "count": count,
    }

@router.get("/api/v1/transactions/me")
def get_transaction_history(
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    return {"items": TransactionModel.find_by_user_id(db_session, current_user_id)}
