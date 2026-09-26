# Project Structure

This repository contains the Student 1 User & Account Service.

- `backend/models/`: SQLAlchemy models representing database tables.
- `backend/schemas/`: Pydantic request and response schemas.
- `backend/controllers/`: FastAPI endpoints. Controllers validate input, call services, and return HTTP responses.
- `backend/services/`: Business logic and database operations.
- `backend/database.py`: SQLAlchemy engine, session factory, and `get_db()` dependency.
- `backend/main.py`: FastAPI application, router registration, CORS, and health check.
- `db/init.sql`: MySQL `account_db` schema and demo seed data.
- `frontend/index.html`: English homepage and project overview.
- `frontend/login.html`: User Service login page.
- `frontend/dashboard.html`: Authenticated user dashboard and workflow placeholders.
- `frontend/profile.html`: Profile page backed by `GET /api/v1/users/me`.
- `frontend/accounts.html`: Simulated AccountDB account list backed by `GET /api/v1/accounts/me`.
- `frontend/tuition.html`: Tuition lookup and payment readiness UI backed by the separate Tuition Service lookup API.
- `frontend/history.html`: Authenticated transaction history UI; records are requested from Payment Service and are not stored in AccountDB.
- `frontend/css/style.css`: Shared responsive styles and navigation presentation.
- `frontend/js/auth.js`: Shared login, API request, navigation, logout, and authentication guard helpers.
- `frontend/js/dashboard.js`, `frontend/js/profile.js`, `frontend/js/accounts.js`, `frontend/js/tuition.js`, `frontend/js/history.js`: Page-specific data loading and UI behavior.
- `tests/`: User Service API and debit concurrency tests.

The frontend uses plain HTML, CSS, and vanilla JavaScript. `frontend/assets/ibanking-hero.png` is the homepage illustration. Tuition lookup connects to the separate Tuition Service. History is an authenticated integration point for the Payment Service; its host and contract are TBD. Payment records remain owned by Payment Service/PaymentDB. The User Service does not access PaymentDB or create transaction records.
