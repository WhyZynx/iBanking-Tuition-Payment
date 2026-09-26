from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Cấu hình kết nối MySQL. 
# Mặc định (như XAMPP) thường dùng user 'root' và không có mật khẩu.
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/payment_db"

# Tạo động cơ kết nối
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Tạo xưởng sản xuất phiên làm việc (Session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Hàm cấp chìa khóa db_session cho Bồi bàn (Controller)
def get_db():
    db = SessionLocal()
    try:
        yield db # Đưa chìa khóa cho Bồi bàn
    finally:
        db.close() # Bồi bàn dùng xong thì tự động thu hồi và đóng cửa kho