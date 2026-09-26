from fastapi import FastAPI
from backend.controllers import paymentController

app = FastAPI(title="Payment Service")

# Đăng ký Bồi bàn Payment vào hệ thống
app.include_router(paymentController.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "payment"}