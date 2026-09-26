# iBanking Tuition Payment

## Student 1: User & Account Service

This repository contains the FastAPI User & Account Service. It owns users, accounts, authentication, and account balance operations. Tuition and payment processing belong to their respective services. Transaction History is a frontend integration point for the Payment Service; this service does not own or store transaction records.

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for the code layout and [docs/USER_SERVICE_API.md](docs/USER_SERVICE_API.md) for the integration contract.

For Student 2 and Student 3 connection details, see [docs/USER_SERVICE_INTEGRATION.md](docs/USER_SERVICE_INTEGRATION.md).

## Run

1. Install Python dependencies: `python -m pip install -r backend/requirements.txt`
2. Create the MySQL schema and seed data: `mysql -u root -p < db/init.sql`
3. Copy `backend/.env.example` to `backend/.env` and set local values.
4. Start the service: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001`
5. Open Swagger at `http://localhost:8001/docs`.

The frontend is a small multi-page HTML/CSS/JavaScript app in `frontend/`. Start at `frontend/index.html`; the tuition page is `frontend/tuition.html`. All pages share styles in `frontend/css/style.css` and helpers in `frontend/js/`. Serve it on port `5500` for the configured User Service CORS origin:

```powershell
python -m http.server 5500 --directory frontend
```

The tuition lookup UI calls the separate Tuition Service at `http://localhost:8002`. History is a frontend integration point; its Payment Service host and API contract are awaiting confirmation from Student 3.

## Tests

```powershell
python -m pytest -q
```
