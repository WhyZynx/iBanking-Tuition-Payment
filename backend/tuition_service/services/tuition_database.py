import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv


load_dotenv(Path(__file__).parents[1] / ".env")


def get_tuition_connection():
    return pymysql.connect(
        host=os.getenv("TUITION_DB_HOST", "localhost"),
        port=int(os.getenv("TUITION_DB_PORT", "3306")),
        user=os.getenv("TUITION_DB_USER", "root"),
        password=os.getenv("TUITION_DB_PASSWORD", ""),
        database=os.getenv(
            "TUITION_DB_NAME",
            "ibanking_tuition"
        ),
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
        autocommit=False
    )
