from os import getenv

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:password@localhost:3306/account_db",
)
JWT_SECRET_KEY = getenv("JWT_SECRET_KEY", "change-this-secret")
JWT_ALGORITHM = getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
INTERNAL_API_KEY = getenv("INTERNAL_API_KEY", "dev-internal-key")
