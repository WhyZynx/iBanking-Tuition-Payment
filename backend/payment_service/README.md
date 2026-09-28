# Payment Service

Entry point: `backend.payment_service.main:app` from the repository root.

```powershell
python -m uvicorn backend.payment_service.main:app --host 0.0.0.0 --port 8003
```

Copy `.env.example` to `.env` in this directory and set local database, service URL, JWT, internal API key, and SMTP values. Payment creation stores a `PENDING` transaction; the OTP endpoint emails a six-digit code, and confirm currently validates/consumes that code without processing the payment. See [../../docs/API_CONTRACTS.md](../../docs/API_CONTRACTS.md).
