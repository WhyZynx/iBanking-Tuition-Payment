from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Cáº¥u hĂ¬nh káº¿t ná»‘i MySQL. 
# Máº·c Ä‘á»‹nh (nhÆ° XAMPP) thÆ°á»ng dĂ¹ng user 'root' vĂ  khĂ´ng cĂ³ máº­t kháº©u.
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/payment_db"

# Táº¡o Ä‘á»™ng cÆ¡ káº¿t ná»‘i
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Táº¡o xÆ°á»Ÿng sáº£n xuáº¥t phiĂªn lĂ m viá»‡c (Session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# HĂ m cáº¥p chĂ¬a khĂ³a db_session cho Bá»“i bĂ n (Controller)
def get_db():
    db = SessionLocal()
    try:
        yield db # ÄÆ°a chĂ¬a khĂ³a cho Bá»“i bĂ n
    finally:
        db.close() # Bá»“i bĂ n dĂ¹ng xong thĂ¬ tá»± Ä‘á»™ng thu há»“i vĂ  Ä‘Ă³ng cá»­a kho
