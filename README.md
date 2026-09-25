# iBanking Tuition Payment

## Student 1: User & Account Service

This repository contains the FastAPI User & Account Service. It owns users, accounts, authentication, and account balance operations. Tuition, payment workflow, OTP, notification, and payment history are outside this service.

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for the code layout and [docs/USER_SERVICE_API.md](docs/USER_SERVICE_API.md) for the integration contract.

## Run

1. Install Python dependencies: `python -m pip install -r backend/requirements.txt`
2. Create the MySQL schema and seed data: `mysql -u root -p < db/init.sql`
3. Copy `backend/.env.example` to `backend/.env` and set local values.
4. Start the service: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001`
5. Open Swagger at `http://localhost:8001/docs`.

The frontend is [frontend/index.html](frontend/index.html). Serve it on port `5500` for the configured local CORS origin.

## Tests

```powershell
python -m pytest -q
```
