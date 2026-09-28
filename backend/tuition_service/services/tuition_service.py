from fastapi import HTTPException
from pymysql import MySQLError

from backend.tuition_service.services.tuition_database import get_tuition_connection

def get_all_tuitions():
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

            return cursor.fetchall()

    except MySQLError as error:
        print("Database error:", error)

        raise HTTPException(
            status_code=500,
            detail="Unable to access tuition database"
        )

    finally:
        if connection:
            connection.close()
            
def get_tuition(student_id: str):
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

        return tuition

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


def mark_tuition_as_paid(student_id: str):
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
