from sqlalchemy import text

class OtpModel:
    @staticmethod
    def verify(db_session, transaction_id, otp_code):
        # TĂ¬m xem cĂ³ mĂ£ OTP nĂ o khá»›p giao dá»‹ch, chÆ°a dĂ¹ng vĂ  chÆ°a háº¿t háº¡n khĂ´ng
        query = text("""
            SELECT * FROM otps 
            WHERE transaction_id = :id 
              AND otp_code = :code 
              AND is_used = False 
              AND expires_at > NOW()
        """)
        result = db_session.execute(query, {"id": transaction_id, "code": otp_code}).fetchone()
        return result # Náº¿u tĂ¬m tháº¥y sáº½ tráº£ vá» dá»¯ liá»‡u, khĂ´ng tháº¥y tráº£ vá» None

    @staticmethod
    def mark_as_used(db_session, otp_id):
        # ÄĂ¡nh dáº¥u Ä‘Ă£ dĂ¹ng báº±ng "cá»¥c táº©y"
        query = text("UPDATE otps SET is_used = True WHERE otp_id = :id")
        db_session.execute(query, {"id": otp_id})
        db_session.commit()
