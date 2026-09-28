from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.payment_service.database import get_db
from backend.payment_service.models.transactionModel import TransactionModel
from backend.payment_service.services.paymentService import PaymentService 

router = APIRouter()
payment_service = PaymentService()

# Äá»‹nh nghÄ©a mĂ³n Äƒn khĂ¡ch gá»i
class ConfirmPaymentRequest(BaseModel):
    transactionId: str
    otpCode: str

# API 1: XĂ¡c nháº­n OTP vĂ  thanh toĂ¡n
@router.post("/api/v1/payments/confirm")
def confirm_payment(request: ConfirmPaymentRequest, db_session: Session = Depends(get_db)):
    """
    Bá»“i bĂ n nháº­n thĂªm db_session vĂ  truyá»n tháº³ng vĂ o báº¿p cho Äáº§u báº¿p
    """
    ket_qua = payment_service.confirm_payment(
        db_session=db_session,  # <--- ChĂ¬a khĂ³a kho Ä‘Æ°á»£c Ä‘Æ°a vĂ o Ä‘Ă¢y
        transaction_id=request.transactionId, 
        otp_code=request.otpCode
    )
    
    if not ket_qua["success"]:
        raise HTTPException(status_code=400, detail=ket_qua["message"])
        
    return {"message": ket_qua["message"]}


# API 2: Láº¥y lá»‹ch sá»­ giao dá»‹ch
@router.get("/api/v1/transactions/me")
def get_transaction_history(request: Request, db_session: Session = Depends(get_db)):
    """
    Bá»“i bĂ n nháº­n db_session vĂ  nhá» Kho nguyĂªn liá»‡u láº¥y danh sĂ¡ch lá»‹ch sá»­
    """
    # Táº¡m thá»i giáº£ Ä‘á»‹nh user Ä‘ang Ä‘Äƒng nháº­p cĂ³ ID lĂ  1
    current_user_id = 1 
    
    history_items = TransactionModel.find_by_user_id(db_session, current_user_id)
    
    return {
        "items": history_items
    }
