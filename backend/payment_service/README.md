# Payment Service

Entry point: `backend.payment_service.main:app` from the repository root.

```powershell
python -m uvicorn backend.payment_service.main:app --host 0.0.0.0 --port 8003
```

Copy `.env.example` to `.env` in this directory and set local database, service URL, JWT, and internal API key values. The payment confirmation route can only process a transaction and OTP already present in PaymentDB; creating payments and coordinating Tuition Service are future workflow work. See [../../docs/API_CONTRACTS.md](../../docs/API_CONTRACTS.md).
