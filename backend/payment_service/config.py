from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

payment_database_url = getenv("PAYMENT_DATABASE_URL")
if not payment_database_url:
    raise RuntimeError("PAYMENT_DATABASE_URL is not configured for Payment Service")
PAYMENT_DATABASE_URL: str = payment_database_url

USER_SERVICE_URL = getenv("USER_SERVICE_URL", "http://localhost:8001").rstrip("/")
TUITION_SERVICE_URL = getenv("TUITION_SERVICE_URL", "http://localhost:8002").rstrip("/")
internal_api_key = getenv("INTERNAL_API_KEY")
if not internal_api_key:
    raise RuntimeError("INTERNAL_API_KEY is not configured for Payment Service")
INTERNAL_API_KEY: str = internal_api_key

jwt_secret_key = getenv("JWT_SECRET_KEY")
if not jwt_secret_key:
    raise RuntimeError("JWT_SECRET_KEY is not configured for Payment Service")
JWT_SECRET_KEY: str = jwt_secret_key

JWT_ALGORITHM: str = getenv("JWT_ALGORITHM") or "HS256"


SMTP_HOST = getenv("SMTP_HOST") or ""
SMTP_USERNAME = getenv("SMTP_USERNAME") or ""
SMTP_PASSWORD = getenv("SMTP_PASSWORD") or ""
SMTP_FROM_EMAIL = getenv("SMTP_FROM_EMAIL") or ""

smtp_port_value: str = getenv("SMTP_PORT") or "587"
SMTP_PORT: int = int(smtp_port_value)