import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TUITION_CLAIM_TTL_SECONDS = int(os.getenv("TUITION_CLAIM_TTL_SECONDS", "300"))
