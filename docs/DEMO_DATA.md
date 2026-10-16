# Dữ liệu demo cục bộ

Bộ seed này dành cho demo local với `account_db` và `ibanking_tuition`. Không chạy lên E2E, shared hoặc production database. Seed không tạo giao dịch/OTP và không cập nhật bản ghi đã có. Mật khẩu chung là `password123`; User Service lưu và kiểm tra bcrypt hash.

| Username | Họ tên | MSSV | Tài khoản | Số dư ban đầu (VND) | Học phí (VND) | Trạng thái đầu |
| --- | --- | --- | --- | ---: | ---: | --- |
| user01 | Nguyen Minh Anh | 524H0001 | 6202000001 | 25,000,000 | 18,500,000 | UNPAID |
| user02 | Tran Ngoc Han | 524H0002 | 6202000002 | 15,000,000 | 16,500,000 | UNPAID |
| user03 | Le Hoang Nam | 524H0003 | 6202000003 | 4,000,000 | 19,000,000 | UNPAID |
| user04 | Pham Gia Linh | 524H0004 | 6202000004 | 30,000,000 | 17,500,000 | UNPAID |
| user05 | Vo Thanh Tung | 723H0001 | 6202000005 | 12,000,000 | 14,000,000 | UNPAID |
| user06 | Do Khanh Vy | 723H0002 | 6202000006 | 20,000,000 | 18,000,000 | PAID |
| user07 | Bui Quoc Bao | 723H0003 | 6202000007 | 8,000,000 | 12,500,000 | UNPAID |
| user08 | Huynh Thao My | 723H0004 | 6202000008 | 35,000,000 | 21,000,000 | UNPAID |

Mỗi tài khoản được thêm là `ACTIVE` và mặc định. Tổng số dư ban đầu là 149,000,000 VND. User và Tuition seed dùng cùng MSSV, họ tên. Các service sở hữu database riêng nên không có khóa ngoại xuyên service. `payment_db` không cần seed.

## Xung đột cần kiểm tra trước

Database có thể đã chứa dữ liệu cũ. Đặc biệt, seed cũ đã dùng username `user01` với tên `Nguyen Van A` và MSSV `524H0104`; bộ mới dùng `Nguyen Minh Anh` và `524H0001`. Nếu bản ghi cũ này còn tồn tại, **không chạy seed User**. Không sửa số dư, xóa hay đổi MSSV để ép seed chạy; hãy dùng một bộ database demo mới hoặc nhờ người quản lý dữ liệu xử lý xung đột thủ công.

Trước khi áp dụng, chạy các truy vấn chỉ đọc sau trong Workbench và kiểm tra kết quả. Nếu username/MSSV/tài khoản hoặc hóa đơn đã tồn tại nhưng không khớp bảng trên, dừng và xử lý thủ công. Kiểm tra cả tài khoản mặc định khác đang gắn với các user này.

```sql
USE account_db;
SELECT user_id, username, full_name, student_id
FROM users
WHERE username IN ('user01','user02','user03','user04','user05','user06','user07','user08')
   OR student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');

SELECT a.account_number, u.username, a.balance, a.is_default, a.status
FROM accounts AS a
JOIN users AS u ON u.user_id = a.user_id
WHERE u.username IN ('user01','user02','user03','user04','user05','user06','user07','user08')
   OR a.account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

USE ibanking_tuition;
SELECT student_id, student_name, amount, status
FROM tuition_bills
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');
```

## Chạy seed trong MySQL Workbench

1. Sao lưu trước và chỉ dùng database demo local đã xác nhận đúng tên. Ưu tiên database demo mới; không áp dụng lên production hoặc database dùng chung.
2. Mở `db/user/demo_seed.sql`, kiểm tra `USE account_db`, rồi chạy sau khi đã kiểm tra xung đột ở trên. Sau đó chạy `db/tuition/demo_seed.sql` với `ibanking_tuition`.
3. Chạy từng seed trong transaction. Nếu có lỗi khóa trùng hoặc lỗi khác, dừng ngay và chạy `ROLLBACK;` trong cùng tab/session trước khi đóng tab. Chỉ để `COMMIT` cuối file chạy khi mọi câu lệnh đều thành công. Giải quyết xung đột thủ công; không xóa hay ghi đè dữ liệu cũ.
4. Có thể chạy lại seed: `WHERE NOT EXISTS` bỏ qua user/bill đã khớp. Tài khoản đã tồn tại không bị reset số dư; hóa đơn đã chuyển từ `UNPAID` sang `PAID` được giữ nguyên. Dữ liệu khác dự kiến gây lỗi khóa trùng để tránh âm thầm bỏ qua xung đột.
5. Xác nhận sau khi chạy bằng các truy vấn `SELECT` ở trên. Không cần thêm giao dịch hay OTP giả.

Nếu Workbench không dừng khi gặp lỗi, chạy các câu lệnh đến trước `COMMIT` riêng theo từng phần; chỉ chạy `COMMIT` sau khi tất cả thành công. Khi có lỗi, chạy `ROLLBACK` ngay.

## Chạy demo bình thường

Seed là tùy chọn. Cấu hình `.env` local từ các file `.env.example`, không đưa credentials vào Git. Dùng database thông thường `account_db`, `ibanking_tuition`, `payment_db`; không cần biến `IBANKING_E2E_*`.

Mở bốn terminal từ thư mục gốc:

```powershell
python -m uvicorn backend.user_service.main:app --host 127.0.0.1 --port 8001
```

```powershell
python -m uvicorn backend.tuition_service.main:app --host 127.0.0.1 --port 8002
```

```powershell
python -m uvicorn backend.payment_service.main:app --host 127.0.0.1 --port 8003
```

```powershell
python -m http.server 5500 --directory frontend
```

Mở `http://localhost:5500`. Các email `example.com` là địa chỉ giả; để demo OTP cần cấu hình một SMTP inbox local/kiểm thử có kiểm soát. Không dùng mailbox thật hoặc đưa SMTP secret vào repository.
