from unittest.mock import patch

from backend.tuition_service.services import tuition_database


def test_tuition_connection_uses_service_database_url(monkeypatch):
    monkeypatch.setattr(
        tuition_database,
        "DATABASE_URL",
        "mysql+pymysql://db_user:test-password@db.example:3307/ibanking_tuition",
    )

    with patch.object(tuition_database.pymysql, "connect") as connect:
        tuition_database.get_tuition_connection()

    connect.assert_called_once_with(
        host="db.example",
        port=3307,
        user="db_user",
        password="test-password",
        database="ibanking_tuition",
        cursorclass=tuition_database.pymysql.cursors.DictCursor,
        charset="utf8mb4",
        autocommit=False,
    )
