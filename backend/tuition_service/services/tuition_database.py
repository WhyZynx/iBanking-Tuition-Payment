from urllib.parse import unquote, urlsplit

import pymysql

from backend.tuition_service.config import DATABASE_URL


def get_tuition_connection() -> pymysql.connections.Connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured for Tuition Service")

    parsed_url = urlsplit(DATABASE_URL)
    if parsed_url.scheme not in {"mysql+pymysql", "mysql"}:
        raise RuntimeError("Tuition Service DATABASE_URL must use MySQL with PyMySQL")

    database_name = unquote(parsed_url.path.lstrip("/"))
    if (
        not parsed_url.hostname
        or not parsed_url.username
        or not parsed_url.password
        or not database_name
    ):
        raise RuntimeError("Tuition Service DATABASE_URL is missing connection details")

    try:
        port = parsed_url.port or 3306
    except ValueError as error:
        raise RuntimeError("Tuition Service DATABASE_URL has an invalid port") from error

    return pymysql.connect(
        host=parsed_url.hostname,
        port=port,
        user=unquote(parsed_url.username),
        password=unquote(parsed_url.password or ""),
        database=database_name,
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
        autocommit=False
    )
