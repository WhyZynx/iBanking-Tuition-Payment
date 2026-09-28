# Giáº£ sá»­ báº¡n cĂ³ import biáº¿n db tá»« file káº¿t ná»‘i cÆ¡ sá»Ÿ dá»¯ liá»‡u cá»§a nhĂ³m
# from backend.payment_service.models.database import db 
from sqlalchemy import text # ThÆ° viá»‡n giĂºp cháº¡y lá»‡nh SQL an toĂ n

class TransactionModel:
    @staticmethod
    def create(db_session, transaction_id, payer_user_id, source_account_number, student_id, amount):
        # 1. CĂ¢u lá»‡nh SQL thĂªm má»›i giao dá»‹ch vá»›i tráº¡ng thĂ¡i PENDING
        query = text("""
            INSERT INTO transactions (transaction_id, payer_user_id, source_account_number, student_id, amount, status, created_at)
            VALUES (:id, :user_id, :account, :student, :amount, 'PENDING', NOW())
        """)
        # 2. Gá»­i dá»¯ liá»‡u vĂ o SQL
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
        # Cáº­p nháº­t tráº¡ng thĂ¡i thĂ nh SUCCESS hoáº·c FAILED
        query = text("UPDATE transactions SET status = :status, completed_at = NOW() WHERE transaction_id = :id")
        db_session.execute(query, {"status": status, "id": transaction_id})
        db_session.commit()

    @staticmethod
    def find_by_id(db_session, transaction_id):
        # TĂ¬m láº¡i giao dá»‹ch Ä‘á»ƒ láº¥y thĂ´ng tin sá»‘ tiá»n, sá»‘ tĂ i khoáº£n
        query = text("SELECT * FROM transactions WHERE transaction_id = :id")
        result = db_session.execute(query, {"id": transaction_id}).fetchone()
        return result
    
    @staticmethod
    def find_by_user_id(db_session, user_id):
        # Truy váº¥n tĂ¬m táº¥t cáº£ giao dá»‹ch cá»§a má»™t user cá»¥ thá»ƒ, sáº¯p xáº¿p má»›i nháº¥t lĂªn Ä‘áº§u
        query = text("""
            SELECT transaction_id, student_id, amount, status, created_at 
            FROM transactions 
            WHERE payer_user_id = :user_id 
            ORDER BY created_at DESC
        """)
        
        # fetchall() sáº½ láº¥y ra toĂ n bá»™ danh sĂ¡ch thay vĂ¬ chá»‰ 1 dĂ²ng nhÆ° fetchone()
        results = db_session.execute(query, {"user_id": user_id}).fetchall()
        
        # Chuyá»ƒn Ä‘á»•i káº¿t quáº£ SQL thĂ nh danh sĂ¡ch dáº¡ng dictionary Ä‘á»ƒ dá»… tráº£ vá» JSON
        history_list = []
        for row in results:
            history_list.append({
                "transactionId": row[0],
                "studentId": row[1],
                # Do Database cá»§a báº¡n chÆ°a lÆ°u studentName, ta táº¡m Ä‘á»ƒ trá»‘ng hoáº·c láº¥y tá»« Tuition Service sau
                "studentName": "N/A", 
                "amount": float(row[2]),
                "status": row[3],
                "createdAt": row[4].isoformat() if row[4] else None
            })
            
        return history_list
