from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

database_url = getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not configured for User Service")
DATABASE_URL: str = database_url

jwt_secret_key = getenv("JWT_SECRET_KEY")
if not jwt_secret_key:
    raise RuntimeError("JWT_SECRET_KEY is not configured for User Service")
JWT_SECRET_KEY: str = jwt_secret_key

JWT_ALGORITHM = getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
internal_api_key = getenv("INTERNAL_API_KEY")
if not internal_api_key:
    raise RuntimeError("INTERNAL_API_KEY is not configured for User Service")
INTERNAL_API_KEY: str = internal_api_key
