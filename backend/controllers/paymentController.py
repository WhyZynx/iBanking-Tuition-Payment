from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.transactionModel import TransactionModel
from backend.services.paymentService import PaymentService 

router = APIRouter()
payment_service = PaymentService()

# Định nghĩa món ăn khách gọi
class ConfirmPaymentRequest(BaseModel):
    transactionId: str
    otpCode: str

# API 1: Xác nhận OTP và thanh toán
@router.post("/api/v1/payments/confirm")
def confirm_payment(request: ConfirmPaymentRequest, db_session: Session = Depends(get_db)):
    """
    Bồi bàn nhận thêm db_session và truyền thẳng vào bếp cho Đầu bếp
    """
    ket_qua = payment_service.confirm_payment(
        db_session=db_session,  # <--- Chìa khóa kho được đưa vào đây
        transaction_id=request.transactionId, 
        otp_code=request.otpCode
    )
    
    if not ket_qua["success"]:
        raise HTTPException(status_code=400, detail=ket_qua["message"])
        
    return {"message": ket_qua["message"]}


# API 2: Lấy lịch sử giao dịch
@router.get("/api/v1/transactions/me")
def get_transaction_history(request: Request, db_session: Session = Depends(get_db)):
    """
    Bồi bàn nhận db_session và nhờ Kho nguyên liệu lấy danh sách lịch sử
    """
    # Tạm thời giả định user đang đăng nhập có ID là 1
    current_user_id = 1 
    
    history_items = TransactionModel.find_by_user_id(db_session, current_user_id)
    
    return {
        "items": history_items
    }