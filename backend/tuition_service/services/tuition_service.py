from fastapi import HTTPException
from pymysql import MySQLError

from backend.tuition_service.models.tuition_model import TuitionBill
from backend.tuition_service.services.tuition_database import get_tuition_connection
from backend.tuition_service.config import TUITION_CLAIM_TTL_SECONDS


def get_all_tuitions() -> list[TuitionBill]:
    connection = None

    try:
        connection = get_tuition_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    student_id,
                    student_name,
                    amount,
                    status
                FROM tuition_bills
                ORDER BY student_id
                """
            )

            return [TuitionBill.model_validate(row) for row in cursor.fetchall()]

    except MySQLError as error:
        print("Database error:", error)

        raise HTTPException(
            status_code=500,
            detail="Unable to access tuition database"
        )

    finally:
        if connection:
            connection.close()
            
def get_tuition(student_id: str) -> TuitionBill:
    student_id = student_id.strip().upper()

    if not student_id:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required"
        )

    connection = None

    try:
        connection = get_tuition_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    student_id,
                    student_name,
                    amount,
                    status
                FROM tuition_bills
                WHERE student_id = %s
                """,
                (student_id,)
            )

            tuition = cursor.fetchone()

        if tuition is None:
            raise HTTPException(
                status_code=404,
                detail="Tuition information not found"
            )

        return TuitionBill.model_validate(tuition)

    except HTTPException:
        raise

    except MySQLError as error:
        print("Database error:", error)

        raise HTTPException(
            status_code=500,
            detail="Unable to access tuition database"
        )

    finally:
        if connection:
            connection.close()


def mark_tuition_as_paid(
    student_id: str,
    transaction_id: str | None = None,
) -> TuitionBill:
    student_id = student_id.strip().upper()

    if not student_id:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required"
        )

    connection = None

    try:
        connection = get_tuition_connection()

        with connection.cursor() as cursor:
            if transaction_id is None:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS claim_count, MAX(transaction_id) AS transaction_id
                    FROM tuition_payment_claims
                    WHERE student_id = %s
                      AND claimed_at >= DATE_SUB(NOW(), INTERVAL %s SECOND)
                    """,
                    (student_id, TUITION_CLAIM_TTL_SECONDS),
                )
            else:
                cursor.execute(
                    """
                    SELECT transaction_id, claimed_at
                    FROM tuition_payment_claims
                    WHERE student_id = %s
                      AND transaction_id = %s
                      AND claimed_at >= DATE_SUB(NOW(), INTERVAL %s SECOND)
                    """,
                    (student_id, transaction_id, TUITION_CLAIM_TTL_SECONDS),
                )
            claim = cursor.fetchone()
            if transaction_id is None:
                if claim is None or claim.get("claim_count", 0) != 1:
                    connection.rollback()
                    cursor.execute(
                        """
                        SELECT status
                        FROM tuition_bills
                        WHERE student_id = %s
                        """,
                        (student_id,),
                    )
                    tuition = cursor.fetchone()
                    if tuition is None:
                        raise HTTPException(
                            status_code=404,
                            detail="Tuition information not found",
                        )
                    if tuition["status"] == "PAID":
                        raise HTTPException(
                            status_code=409,
                            detail="Tuition has already been paid",
                        )
                    raise HTTPException(
                        status_code=409,
                        detail="No active tuition payment claim for this student",
                    )
                transaction_id = claim["transaction_id"]
            if claim is None:
                connection.rollback()
                cursor.execute(
                    """
                    SELECT status
                    FROM tuition_bills
                    WHERE student_id = %s
                    """,
                    (student_id,),
                )
                tuition = cursor.fetchone()
                if tuition is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Tuition information not found",
                    )
                if tuition["status"] == "PAID":
                    raise HTTPException(
                        status_code=409,
                        detail="Tuition has already been paid",
                    )
                raise HTTPException(
                    status_code=409,
                    detail="No active tuition payment claim for this transaction",
                )

            cursor.execute(
                """
                UPDATE tuition_bills
                SET status = 'PAID'
                WHERE student_id = %s
                  AND status = 'UNPAID'
                """,
                (student_id,)
            )

            if cursor.rowcount == 0:
                connection.rollback()

                cursor.execute(
                    """
                    SELECT status
                    FROM tuition_bills
                    WHERE student_id = %s
                    """,
                    (student_id,)
                )

                tuition = cursor.fetchone()

                if tuition is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Tuition information not found"
                    )

                raise HTTPException(
                    status_code=409,
                    detail="Tuition has already been paid"
                )

            cursor.execute(
                """
                DELETE FROM tuition_payment_claims
                WHERE student_id = %s AND transaction_id = %s
                """,
                (student_id, transaction_id)
            )

        connection.commit()

        return get_tuition(student_id)

    except HTTPException:
        raise

    except MySQLError as error:
        if connection:
            connection.rollback()

        print("Database error:", error)

        raise HTTPException(
            status_code=500,
            detail="Unable to update tuition"
        )

    finally:
        if connection:
            connection.close()


def claim_tuition_payment(student_id: str, transaction_id: str):
    student_id = student_id.strip().upper()
    if not student_id:
        raise HTTPException(status_code=400, detail="Student ID is required")

    connection = None
    try:
        connection = get_tuition_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT transaction_id, claimed_at
                FROM tuition_payment_claims
                WHERE student_id = %s
                  AND claimed_at < DATE_SUB(NOW(), INTERVAL %s SECOND)
                """,
                (student_id, TUITION_CLAIM_TTL_SECONDS),
            )
            expired_claim = cursor.fetchone()
            if expired_claim is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Tuition payment claim expired; release or reconcile it before retrying",
                )

            cursor.execute(
                """
                INSERT IGNORE INTO tuition_payment_claims (student_id, transaction_id)
                SELECT student_id, %s
                FROM tuition_bills
                WHERE student_id = %s AND status = 'UNPAID'
                """,
                (transaction_id, student_id)
            )
            if cursor.rowcount == 1:
                connection.commit()
                return {"student_id": student_id, "transaction_id": transaction_id}

            connection.rollback()
            cursor.execute(
                "SELECT status FROM tuition_bills WHERE student_id = %s",
                (student_id,)
            )
            tuition = cursor.fetchone()
            if tuition is None:
                raise HTTPException(status_code=404, detail="Tuition information not found")
            if tuition["status"] == "PAID":
                raise HTTPException(status_code=409, detail="Tuition has already been paid")
            raise HTTPException(status_code=409, detail="Tuition payment is already being processed")
    except HTTPException:
        raise
    except MySQLError as error:
        if connection:
            connection.rollback()
        print("Database error while claiming tuition payment:", error)
        raise HTTPException(status_code=500, detail="Unable to claim tuition payment")
    finally:
        if connection:
            connection.close()


def release_tuition_payment_claim(student_id: str, transaction_id: str):
    student_id = student_id.strip().upper()
    connection = None
    try:
        connection = get_tuition_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM tuition_payment_claims
                WHERE student_id = %s AND transaction_id = %s
                """,
                (student_id, transaction_id)
            )
            released = cursor.rowcount == 1
        connection.commit()
        return {"released": released}
    except MySQLError as error:
        if connection:
            connection.rollback()
        print("Database error while releasing tuition payment claim:", error)
        raise HTTPException(status_code=500, detail="Unable to release tuition payment claim")
    finally:
        if connection:
            connection.close()


def get_tuition_payment_claim_status(student_id: str, transaction_id: str):
    student_id = student_id.strip().upper()
    transaction_id = transaction_id.strip()

    if not student_id:
        raise HTTPException(status_code=400, detail="Student ID is required")
    if not transaction_id:
        raise HTTPException(status_code=400, detail="Transaction ID is required")

    connection = None
    try:
        connection = get_tuition_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    claimed_at >= DATE_SUB(
                        NOW(),
                        INTERVAL %s SECOND
                    ) AS is_active
                FROM tuition_payment_claims
                WHERE student_id = %s AND transaction_id = %s
                """,
                (TUITION_CLAIM_TTL_SECONDS, student_id, transaction_id),
            )
            claim = cursor.fetchone()

        if claim is None:
            return {
                "student_id": student_id,
                "transaction_id": transaction_id,
                "state": "NOT_FOUND",
                "active": False,
            }

        active = bool(claim["is_active"])
        return {
            "student_id": student_id,
            "transaction_id": transaction_id,
            "state": "ACTIVE" if active else "EXPIRED",
            "active": active,
        }
    except MySQLError as error:
        print("Database error while checking tuition payment claim:", error)
        raise HTTPException(
            status_code=500,
            detail="Unable to check tuition payment claim",
        )
    finally:
        if connection:
            connection.close()
