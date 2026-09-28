import json

import requests

from backend.payment_service.config import INTERNAL_API_KEY, USER_SERVICE_URL

# Import Ä‘Ăºng class tá»« cĂ¡c file model cá»§a báº¡n
from backend.payment_service.models.otpModel import OtpModel
from backend.payment_service.models.transactionModel import TransactionModel

class PaymentService:
    # 1. ThĂªm db_session vĂ o hĂ m Ä‘á»ƒ Äáº§u báº¿p cĂ³ chĂ¬a khĂ³a má»Ÿ kho
    def confirm_payment(self, db_session, transaction_id, otp_code):
        
        # 2. Truyá»n db_session vĂ o hĂ m verify()
        otp_record = OtpModel.verify(db_session, transaction_id, otp_code)
        if not otp_record:
            return {"success": False, "message": "MĂ£ OTP sai hoáº·c Ä‘Ă£ háº¿t háº¡n!"}

        # 3. Truyá»n db_session vĂ o hĂ m find_by_id()
        transaction = TransactionModel.find_by_id(db_session, transaction_id)
        
        # "Gá»i Ä‘iá»‡n" sang User Service nhá» trá»« tiá»n
        user_service_url = f"{USER_SERVICE_URL}/api/v1/internal/accounts/{transaction.source_account_number}/debit"
        headers = {
            "X-Internal-API-Key": INTERNAL_API_KEY # MĂ£ bĂ­ máº­t Ä‘á»ƒ User Service cho phĂ©p trá»« tiá»n
        }
        payload = (
            f'{{"amount":{transaction.amount},'
            f'"transactionId":{json.dumps(transaction_id)}}}'
        )

        # Thá»±c hiá»‡n cuá»™c gá»i API 
        headers["Content-Type"] = "application/json"
        response = requests.post(user_service_url, data=payload, headers=headers)

        # Xá»­ lĂ½ káº¿t quáº£ tá»« User Service
        if response.status_code == 200:
            # 4. Truyá»n db_session vĂ o cĂ¡c hĂ m cáº­p nháº­t
            TransactionModel.update_status(db_session, transaction_id, "SUCCESS")
            OtpModel.mark_as_used(db_session, otp_record.otp_id) 
            
            return {"success": True, "message": "Thanh toĂ¡n thĂ nh cĂ´ng!"}
        else:
            TransactionModel.update_status(db_session, transaction_id, "FAILED")
            return {"success": False, "message": "Sá»‘ dÆ° khĂ´ng Ä‘á»§ hoáº·c lá»—i tĂ i khoáº£n!"}
