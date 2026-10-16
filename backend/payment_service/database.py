from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.payment_service.config import PAYMENT_DATABASE_URL

# Cáº¥u hĂ¬nh káº¿t ná»‘i MySQL. 
# Máº·c Ä‘á»‹nh (nhÆ° XAMPP) thÆ°á»ng dĂ¹ng user 'root' vĂ  khĂ´ng cĂ³ máº­t kháº©u.

# Táº¡o Ä‘á»™ng cÆ¡ káº¿t ná»‘i
engine = create_engine(PAYMENT_DATABASE_URL)

# Táº¡o xÆ°á»Ÿng sáº£n xuáº¥t phiĂªn lĂ m viá»‡c (Session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# HĂ m cáº¥p chĂ¬a khĂ³a db_session cho Bá»“i bĂ n (Controller)
def get_db():
    db = SessionLocal()
    try:
        yield db # ÄÆ°a chĂ¬a khĂ³a cho Bá»“i bĂ n
    finally:
        db.close() # Bá»“i bĂ n dĂ¹ng xong thĂ¬ tá»± Ä‘á»™ng thu há»“i vĂ  Ä‘Ă³ng cá»­a kho
