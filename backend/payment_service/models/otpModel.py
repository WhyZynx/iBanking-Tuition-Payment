from sqlalchemy import text


class OtpModel:
    @staticmethod
    def is_active_code(db_session, otp_code):
        query = text("""
            SELECT otp_id
            FROM otps
            WHERE otp_code = :code
              AND is_used = FALSE
              AND expires_at > CURRENT_TIMESTAMP
            LIMIT 1
        """)
        return db_session.execute(query, {"code": otp_code}).fetchone() is not None

    @staticmethod
    def create(db_session, transaction_id, otp_code, expires_at):
        db_session.execute(
            text("""
                UPDATE otps
                SET is_used = TRUE
                WHERE transaction_id = :transaction_id
                  AND is_used = FALSE
                  AND expires_at > CURRENT_TIMESTAMP
            """),
            {"transaction_id": transaction_id},
        )
        result = db_session.execute(
            text("""
                INSERT INTO otps (transaction_id, otp_code, expires_at, is_used)
                VALUES (:transaction_id, :otp_code, :expires_at, FALSE)
            """),
            {
                "transaction_id": transaction_id,
                "otp_code": otp_code,
                "expires_at": expires_at,
            },
        )
        db_session.commit()
        return result.lastrowid

    @staticmethod
    def verify(db_session, transaction_id, otp_code):
        query = text("""
            SELECT * FROM otps
            WHERE transaction_id = :id
              AND otp_code = :code
              AND is_used = FALSE
              AND expires_at > CURRENT_TIMESTAMP
            ORDER BY otp_id DESC
            LIMIT 1
        """)
        return db_session.execute(
            query,
            {"id": transaction_id, "code": otp_code},
        ).fetchone()

    @staticmethod
    def mark_as_used(db_session, otp_id):
        query = text("""
            UPDATE otps
            SET is_used = TRUE
            WHERE otp_id = :id
              AND is_used = FALSE
              AND expires_at > CURRENT_TIMESTAMP
        """)
        result = db_session.execute(query, {"id": otp_id})
        db_session.commit()
        return result.rowcount == 1
