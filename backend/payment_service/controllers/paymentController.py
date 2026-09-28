from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.payment_service.config import JWT_ALGORITHM, JWT_SECRET_KEY
from backend.payment_service.database import get_db
from backend.payment_service.models.transactionModel import TransactionModel
from backend.payment_service.services.paymentService import PaymentService


router = APIRouter()
payment_service = PaymentService()
bearer_scheme = HTTPBearer(auto_error=False)


class ConfirmPaymentRequest(BaseModel):
    transactionId: str
    otpCode: str


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


@router.post("/api/v1/payments/confirm")
def confirm_payment(
    request: ConfirmPaymentRequest,
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    transaction = TransactionModel.find_by_id(db_session, request.transactionId)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.payer_user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transaction does not belong to the authenticated user")

    result = payment_service.confirm_payment(
        db_session=db_session,
        transaction_id=request.transactionId,
        otp_code=request.otpCode,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return {"message": result["message"]}


@router.get("/api/v1/transactions/me")
def get_transaction_history(
    current_user_id: int = Depends(get_current_user_id),
    db_session: Session = Depends(get_db),
):
    return {"items": TransactionModel.find_by_user_id(db_session, current_user_id)}
