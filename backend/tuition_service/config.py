import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
