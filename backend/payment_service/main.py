from fastapi import FastAPI
from backend.payment_service.controllers import paymentController

app = FastAPI(title="Payment Service")

# ÄÄƒng kĂ½ Bá»“i bĂ n Payment vĂ o há»‡ thá»‘ng
app.include_router(paymentController.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "payment"}
