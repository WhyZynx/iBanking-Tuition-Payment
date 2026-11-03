from fastapi import HTTPException, status
from pymysql import MySQLError

from backend.tuition_service.controllers.tuition_controller import app
from backend.tuition_service.services.tuition_database import get_tuition_connection


@app.get("/health", tags=["Health"], summary="Check service and database health")
def health() -> dict[str, str]:
    connection = None
    try:
        connection = get_tuition_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except (MySQLError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tuition database is unavailable",
        ) from error
    finally:
        if connection:
            connection.close()
    return {"status": "ok"}
