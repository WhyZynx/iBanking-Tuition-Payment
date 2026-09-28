# iBanking Tuition Payment

Three independent FastAPI services and a shared static frontend.

| Service | Entry point | Port | Database |
|---|---|---:|---|
| User & Account | `backend.user_service.main:app` | 8001 | `account_db` |
| Tuition | `backend.tuition_service.main:app` | 8002 | `ibanking_tuition` |
| Payment | `backend.payment_service.main:app` | 8003 | `payment_db` |

Run each service from the repository root with `python -m uvicorn <entry-point> --host 0.0.0.0 --port <port>`. The frontend is served on port 5500. Service API contracts and current integration gaps are documented in [docs/API_CONTRACTS.md](docs/API_CONTRACTS.md).

Install dependencies separately from each service's `requirements.txt`. Copy the relevant `.env.example` to that service directory's local `.env`; do not commit secrets.
