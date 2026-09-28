from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

PAYMENT_DATABASE_URL = getenv(
    "PAYMENT_DATABASE_URL",
    "mysql+pymysql://root:@localhost:3306/payment_db",
)
USER_SERVICE_URL = getenv("USER_SERVICE_URL", "http://localhost:8001").rstrip("/")
TUITION_SERVICE_URL = getenv("TUITION_SERVICE_URL", "http://localhost:8002").rstrip("/")
INTERNAL_API_KEY = getenv("INTERNAL_API_KEY", "change-this-internal-key")
JWT_SECRET_KEY = getenv("JWT_SECRET_KEY", "change-this-secret")
JWT_ALGORITHM = getenv("JWT_ALGORITHM", "HS256")
