from backend.tuition_service.controllers.tuition_controller import app
from backend.tuition_service.services.tuition_database import get_tuition_connection


@app.get("/health", tags=["Health"], summary="Check service and database health")
def health() -> dict[str, str]:
    connection = get_tuition_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        connection.close()
    return {"status": "ok"}
