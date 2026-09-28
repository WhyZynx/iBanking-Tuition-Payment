from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.payment_service.controllers import paymentController

app = FastAPI(title="Payment Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ÄÄƒng kĂ½ Bá»“i bĂ n Payment vĂ o há»‡ thá»‘ng
app.include_router(paymentController.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "payment"}
