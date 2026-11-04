from datetime import datetime, timedelta, timezone

from sqlalchemy import text


PROCESSING_TIMEOUT = timedelta(seconds=90)


def serialize_utc_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


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
              AND status IN ('PENDING', 'PROCESSING', 'RECONCILIATION_REQUIRED')
            LIMIT 1
        """)
        return db_session.execute(
            query,
            {
                "user_id": payer_user_id,
                "student_id": student_id,
            },
        ).fetchone()

    @staticmethod
    def fail_pending_by_user_id(db_session, payer_user_id):
        query = text("""
            UPDATE transactions
            SET status = 'FAILED',
                completed_at = CURRENT_TIMESTAMP
            WHERE payer_user_id = :user_id
              AND status = 'PENDING'
        """)
        result = db_session.execute(
            query,
            {"user_id": payer_user_id},
        )
        db_session.commit()
        return result.rowcount

    @staticmethod
    def fail_expired_pending(db_session):
        query = text("""
            UPDATE transactions
            SET status = 'FAILED',
                completed_at = CURRENT_TIMESTAMP
            WHERE status = 'PENDING'
              AND created_at < NOW() - INTERVAL 5 MINUTE
              AND NOT EXISTS (
                  SELECT 1
                  FROM otps
                  WHERE otps.transaction_id = transactions.transaction_id
                    AND otps.is_used = FALSE
                    AND otps.expires_at > CURRENT_TIMESTAMP
              )
        """)
        result = db_session.execute(query)
        db_session.commit()
        return result.rowcount

    @staticmethod
    def update_status(db_session, transaction_id, status):
        query = text(
            "UPDATE transactions "
            "SET status = :status, completed_at = CURRENT_TIMESTAMP, "
            "reconciliation_code = NULL "
            "WHERE transaction_id = :id AND status = 'PROCESSING'"
        )
        result = db_session.execute(
            query,
            {
                "status": status,
                "id": transaction_id,
            },
        )
        db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def fail_pending(db_session, transaction_id, commit=True):
        result = db_session.execute(
            text("""
                UPDATE transactions
                SET status = 'FAILED',
                    completed_at = CURRENT_TIMESTAMP
                WHERE transaction_id = :id
                  AND status = 'PENDING'
            """),
            {"id": transaction_id},
        )
        if commit:
            db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def mark_reconciliation_required(db_session, transaction_id, reason_code=None):
        result = db_session.execute(
            text("""
                UPDATE transactions
                SET status = 'RECONCILIATION_REQUIRED',
                    completed_at = NULL,
                    reconciliation_code = :reason_code
                WHERE transaction_id = :id
                  AND status = 'PROCESSING'
            """),
            {"id": transaction_id, "reason_code": reason_code},
        )
        db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def claim_reconciliation_for_processing(db_session, transaction_id, payer_user_id):
        result = db_session.execute(
            text("""
                UPDATE transactions
                SET status = 'PROCESSING',
                    completed_at = CURRENT_TIMESTAMP
                WHERE transaction_id = :id
                  AND payer_user_id = :user_id
                  AND status = 'RECONCILIATION_REQUIRED'
                  AND reconciliation_code IS NULL
            """),
            {
                "id": transaction_id,
                "user_id": payer_user_id,
            },
        )
        db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def update_processing_amount(db_session, transaction_id, amount):
        result = db_session.execute(
            text("""
                UPDATE transactions
                SET amount = :amount
                WHERE transaction_id = :id
                  AND status = 'PROCESSING'
            """),
            {
                "amount": amount,
                "id": transaction_id,
            },
        )
        db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def mark_stale_processing_for_reconciliation(
        db_session,
        transaction_id=None,
        payer_user_id=None,
    ):
        if transaction_id is None and payer_user_id is None:
            return 0

        cutoff = (datetime.now(timezone.utc) - PROCESSING_TIMEOUT).replace(tzinfo=None)
        result = db_session.execute(
            text("""
                UPDATE transactions
                SET status = 'RECONCILIATION_REQUIRED',
                    completed_at = NULL
                WHERE status = 'PROCESSING'
                  AND completed_at IS NOT NULL
                  AND completed_at <= :cutoff
                  AND (:transaction_id IS NULL OR transaction_id = :transaction_id)
                  AND (:payer_user_id IS NULL OR payer_user_id = :payer_user_id)
            """),
            {
                "cutoff": cutoff,
                "transaction_id": transaction_id,
                "payer_user_id": payer_user_id,
            },
        )
        db_session.commit()
        return result.rowcount

    @staticmethod
    def claim_for_processing(db_session, transaction_id, payer_user_id):
        result = db_session.execute(
            text("""
                UPDATE transactions
                SET status = 'PROCESSING',
                    completed_at = CURRENT_TIMESTAMP
                WHERE transaction_id = :id
                  AND payer_user_id = :user_id
                  AND status = 'PENDING'
            """),
            {
                "id": transaction_id,
                "user_id": payer_user_id,
            },
        )
        db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def release_processing(db_session, transaction_id):
        result = db_session.execute(
            text("""
                UPDATE transactions
                                SET status = 'PENDING',
                                        completed_at = NULL
                WHERE transaction_id = :id
                  AND status = 'PROCESSING'
            """),
            {"id": transaction_id},
        )
        db_session.commit()
        return result.rowcount == 1

    @staticmethod
    def complete(db_session, transaction_id, amount):
        completed_at = datetime.now(timezone.utc)
        query = text("""
            UPDATE transactions
            SET amount = :amount,
                status = 'SUCCESS',
                completed_at = :completed_at,
                reconciliation_code = NULL
            WHERE transaction_id = :id
              AND status = 'PROCESSING'
        """)
        result = db_session.execute(
            query,
            {
                "amount": amount,
                "completed_at": completed_at,
                "id": transaction_id,
            },
        )
        db_session.commit()

        if result.rowcount != 1:
            return None

        return completed_at

    @staticmethod
    def find_by_id(db_session, transaction_id):
        query = text(
            "SELECT * FROM transactions WHERE transaction_id = :id"
        )
        return db_session.execute(
            query,
            {"id": transaction_id},
        ).fetchone()

    @staticmethod
    def find_by_user_id(db_session, user_id):
        TransactionModel.fail_expired_pending(db_session)
        TransactionModel.mark_stale_processing_for_reconciliation(
            db_session,
            payer_user_id=user_id,
        )

        query = text("""
            SELECT transaction_id,
                   student_id,
                   student_name,
                   source_account_number,
                   amount,
                   status,
                   created_at,
                   completed_at
            FROM transactions
            WHERE payer_user_id = :user_id
            ORDER BY created_at DESC
        """)

        results = db_session.execute(
            query,
            {"user_id": user_id},
        ).fetchall()

        return [
            {
                "transactionId": row[0],
                "studentId": row[1],
                "studentName": row[2] or "N/A",
                "sourceAccountNumber": row[3],
                "amount": row[4],
                "status": row[5],
                "createdAt": serialize_utc_datetime(row[6]),
                "completedAt": (
                    serialize_utc_datetime(row[7])
                    if row[7] and row[5] in ("SUCCESS", "FAILED")
                    else None
                ),
            }
            for row in results
        ]
