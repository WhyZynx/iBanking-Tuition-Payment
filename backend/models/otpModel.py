from sqlalchemy import text

class OtpModel:
    @staticmethod
    def verify(db_session, transaction_id, otp_code):
        # Tìm xem có mã OTP nào khớp giao dịch, chưa dùng và chưa hết hạn không
        query = text("""
            SELECT * FROM otps 
            WHERE transaction_id = :id 
              AND otp_code = :code 
              AND is_used = False 
              AND expires_at > NOW()
        """)
        result = db_session.execute(query, {"id": transaction_id, "code": otp_code}).fetchone()
        return result # Nếu tìm thấy sẽ trả về dữ liệu, không thấy trả về None

    @staticmethod
    def mark_as_used(db_session, otp_id):
        # Đánh dấu đã dùng bằng "cục tẩy"
        query = text("UPDATE otps SET is_used = True WHERE otp_id = :id")
        db_session.execute(query, {"id": otp_id})
        db_session.commit()