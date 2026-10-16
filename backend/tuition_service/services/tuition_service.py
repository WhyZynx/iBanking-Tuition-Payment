from fastapi import HTTPException
from pymysql import MySQLError

from backend.tuition_service.models.tuition_model import TuitionBill
from backend.tuition_service.services.tuition_database import get_tuition_connection


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


def mark_tuition_as_paid(student_id: str) -> TuitionBill:
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
                "DELETE FROM tuition_payment_claims WHERE student_id = %s",
                (student_id,)
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
