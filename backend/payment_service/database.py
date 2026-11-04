from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.payment_service.config import PAYMENT_DATABASE_URL

engine = create_engine(PAYMENT_DATABASE_URL)
if engine.dialect.name == "mysql":
    @event.listens_for(engine, "connect")
    def set_mysql_session_timezone(dbapi_connection, _connection_record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+07:00'")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db 
    finally:
        db.close() 
