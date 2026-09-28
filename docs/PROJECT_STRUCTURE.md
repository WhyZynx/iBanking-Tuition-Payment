# Project Structure

The repository contains three independent services under `backend/user_service/`, `backend/tuition_service/`, and `backend/payment_service/`, with database initialization under `db/user/`, `db/tuition/`, and `db/payment/`.

The User Service includes controllers, services, SQLAlchemy models, Pydantic schemas, authentication/security, and database configuration. Tuition and Payment have their own controller/model/service/database layers. Frontend pages live in `frontend/`; tests are grouped under `tests/user_service/` and `tests/tuition_service/`.

See [API contracts](API_CONTRACTS.md) for current endpoint shapes, authentication, service URLs, ownership, and remaining integration work.
