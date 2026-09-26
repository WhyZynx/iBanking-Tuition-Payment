# Giả sử bạn có import biến db từ file kết nối cơ sở dữ liệu của nhóm
# from backend.database import db 
from sqlalchemy import text # Thư viện giúp chạy lệnh SQL an toàn

class TransactionModel:
    @staticmethod
    def create(db_session, transaction_id, payer_user_id, source_account_number, student_id, amount):
        # 1. Câu lệnh SQL thêm mới giao dịch với trạng thái PENDING
        query = text("""
            INSERT INTO transactions (transaction_id, payer_user_id, source_account_number, student_id, amount, status, created_at)
            VALUES (:id, :user_id, :account, :student, :amount, 'PENDING', NOW())
        """)
        # 2. Gửi dữ liệu vào SQL
        db_session.execute(query, {
            "id": transaction_id, 
            "user_id": payer_user_id, 
            "account": source_account_number, 
            "student": student_id, 
            "amount": amount
        })
        db_session.commit()
        return transaction_id

    @staticmethod
    def update_status(db_session, transaction_id, status):
        # Cập nhật trạng thái thành SUCCESS hoặc FAILED
        query = text("UPDATE transactions SET status = :status, completed_at = NOW() WHERE transaction_id = :id")
        db_session.execute(query, {"status": status, "id": transaction_id})
        db_session.commit()

    @staticmethod
    def find_by_id(db_session, transaction_id):
        # Tìm lại giao dịch để lấy thông tin số tiền, số tài khoản
        query = text("SELECT * FROM transactions WHERE transaction_id = :id")
        result = db_session.execute(query, {"id": transaction_id}).fetchone()
        return result
    
    @staticmethod
    def find_by_user_id(db_session, user_id):
        # Truy vấn tìm tất cả giao dịch của một user cụ thể, sắp xếp mới nhất lên đầu
        query = text("""
            SELECT transaction_id, student_id, amount, status, created_at 
            FROM transactions 
            WHERE payer_user_id = :user_id 
            ORDER BY created_at DESC
        """)
        
        # fetchall() sẽ lấy ra toàn bộ danh sách thay vì chỉ 1 dòng như fetchone()
        results = db_session.execute(query, {"user_id": user_id}).fetchall()
        
        # Chuyển đổi kết quả SQL thành danh sách dạng dictionary để dễ trả về JSON
        history_list = []
        for row in results:
            history_list.append({
                "transactionId": row[0],
                "studentId": row[1],
                # Do Database của bạn chưa lưu studentName, ta tạm để trống hoặc lấy từ Tuition Service sau
                "studentName": "N/A", 
                "amount": float(row[2]),
                "status": row[3],
                "createdAt": row[4].isoformat() if row[4] else None
            })
            
        return history_list