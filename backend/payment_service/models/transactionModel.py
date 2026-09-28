from sqlalchemy import text


class TransactionModel:
    @staticmethod
    def create(
        db_session,
        transaction_id,
        payer_user_id,
        source_account_number,
        student_id,
        amount,
        student_name=None,
    ):
        query = text("""
            INSERT INTO transactions (
                transaction_id, payer_user_id, source_account_number,
                student_id, student_name, amount, status, created_at
            )
            VALUES (
                :id, :user_id, :account, :student,
                :student_name, :amount, 'PENDING', NOW()
            )
        """)
        db_session.execute(query, {
            "id": transaction_id,
            "user_id": payer_user_id,
            "account": source_account_number,
            "student": student_id,
            "student_name": student_name,
            "amount": amount,
        })
        db_session.commit()
        return transaction_id

    @staticmethod
    def find_pending_by_user_and_student(db_session, payer_user_id, student_id):
        query = text("""
            SELECT transaction_id
            FROM transactions
            WHERE payer_user_id = :user_id
              AND student_id = :student_id
              AND status = 'PENDING'
            LIMIT 1
        """)
        return db_session.execute(
            query,
            {"user_id": payer_user_id, "student_id": student_id},
        ).fetchone()

    @staticmethod
    def update_status(db_session, transaction_id, status):
        query = text(
            "UPDATE transactions SET status = :status, completed_at = NOW() "
            "WHERE transaction_id = :id"
        )
        db_session.execute(query, {"status": status, "id": transaction_id})
        db_session.commit()

    @staticmethod
    def find_by_id(db_session, transaction_id):
        query = text("SELECT * FROM transactions WHERE transaction_id = :id")
        return db_session.execute(query, {"id": transaction_id}).fetchone()

    @staticmethod
    def find_by_user_id(db_session, user_id):
        query = text("""
            SELECT transaction_id, student_id, student_name, amount, status, created_at
            FROM transactions
            WHERE payer_user_id = :user_id
            ORDER BY created_at DESC
        """)
        results = db_session.execute(query, {"user_id": user_id}).fetchall()
        return [
            {
                "transactionId": row[0],
                "studentId": row[1],
                "studentName": row[2] or "N/A",
                "amount": row[3],
                "status": row[4],
                "createdAt": row[5].isoformat() if row[5] else None,
            }
            for row in results
        ]
