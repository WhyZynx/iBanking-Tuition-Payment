# Project Structure

This repository contains the Student 1 User & Account Service.

- `backend/models/`: SQLAlchemy models representing database tables.
- `backend/schemas/`: Pydantic request and response schemas.
- `backend/controllers/`: FastAPI endpoints. Controllers validate input, call services, and return HTTP responses.
- `backend/services/`: Business logic and database operations.
- `backend/database.py`: SQLAlchemy engine, session factory, and `get_db()` dependency.
- `backend/main.py`: FastAPI application, router registration, CORS, and health check.
- `db/init.sql`: MySQL `account_db` schema and demo seed data.
- `frontend/index.html`: Vanilla HTML/CSS/JavaScript login and account dashboard.
- `tests/`: User Service API and debit concurrency tests.

The service does not own tuition or payment transaction data.