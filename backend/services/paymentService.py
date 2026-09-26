import requests

# Import đúng class từ các file model của bạn
from backend.models.otpModel import OtpModel
from backend.models.transactionModel import TransactionModel

class PaymentService:
    # 1. Thêm db_session vào hàm để Đầu bếp có chìa khóa mở kho
    def confirm_payment(self, db_session, transaction_id, otp_code):
        
        # 2. Truyền db_session vào hàm verify()
        otp_record = OtpModel.verify(db_session, transaction_id, otp_code)
        if not otp_record:
            return {"success": False, "message": "Mã OTP sai hoặc đã hết hạn!"}

        # 3. Truyền db_session vào hàm find_by_id()
        transaction = TransactionModel.find_by_id(db_session, transaction_id)
        
        # "Gọi điện" sang User Service nhờ trừ tiền
        user_service_url = f"http://localhost:8001/api/v1/internal/accounts/{transaction.source_account_number}/debit"
        headers = {
            "X-Internal-API-Key": "my-secret-key" # Mã bí mật để User Service cho phép trừ tiền
        }
        payload = {
            "amount": float(transaction.amount),
            "transactionId": transaction_id
        }

        # Thực hiện cuộc gọi API 
        response = requests.post(user_service_url, json=payload, headers=headers)

        # Xử lý kết quả từ User Service
        if response.status_code == 200:
            # 4. Truyền db_session vào các hàm cập nhật
            TransactionModel.update_status(db_session, transaction_id, "SUCCESS")
            OtpModel.mark_as_used(db_session, otp_record.otp_id) 
            
            return {"success": True, "message": "Thanh toán thành công!"}
        else:
            TransactionModel.update_status(db_session, transaction_id, "FAILED")
            return {"success": False, "message": "Số dư không đủ hoặc lỗi tài khoản!"}