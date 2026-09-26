import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_user_service.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["INTERNAL_API_KEY"] = "test-internal-key"

import pytest
from fastapi.testclient import TestClient

from backend.database import Base, SessionLocal, engine
from backend.main import app
from backend.models import Account, User
from backend.security import hash_password


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    user = User(
        username="user01",
        password_hash=hash_password("123456"),
        full_name="Nguyen Van A",
        phone="0901234567",
        email="user01@example.com",
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            Account(account_number="1012345678", user_id=user.user_id, balance=Decimal("15000000"), is_default=True),
            Account(account_number="1012345679", user_id=user.user_id, balance=Decimal("5000000"), is_default=False),
            Account(account_number="1000000000", user_id=user.user_id, balance=Decimal("0"), status="INACTIVE"),
        ]
    )
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    Path("test_user_service.db").unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient) -> str:
    response = client.post("/api/v1/auth/login", json={"username": "user01", "password": "123456"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_and_profile(client: TestClient):
    token = login(client)
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {
        "userId": 1,
        "username": "user01",
        "fullName": "Nguyen Van A",
        "phone": "0901234567",
        "email": "user01@example.com",
    }
    assert "password" not in response.text
    assert "password_hash" not in response.text


def test_invalid_login_and_missing_token(client: TestClient):
    assert client.post("/api/v1/auth/login", json={"username": "user01", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "missing", "password": "123456"}).status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid-token"}).status_code == 401


def test_accounts_are_scoped_to_current_user(client: TestClient):
    db = SessionLocal()
    other_user = User(
        username="user02",
        password_hash=hash_password("other-password"),
        full_name="Nguyen Van B",
        phone="0900000000",
        email="user02@example.com",
    )
    db.add(other_user)
    db.flush()
    db.add(Account(account_number="2012345678", user_id=other_user.user_id, balance=Decimal("9000000")))
    db.commit()
    db.close()

    token = login(client)
    response = client.get("/api/v1/accounts/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert [account["accountNumber"] for account in response.json()] == ["1012345678", "1000000000", "1012345679"]
    assert "2012345678" not in response.text


def test_internal_lookup_and_debit(client: TestClient):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    lookup = client.get("/api/v1/internal/accounts/1012345678", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["balance"] == 15000000

    debit = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers=headers,
        json={"amount": 8500000, "transactionId": "TX-001"},
    )
    assert debit.status_code == 200
    assert debit.json() == {"success": True, "accountNumber": "1012345678", "remainingBalance": 6500000}


def test_debit_rejects_invalid_cases(client: TestClient):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    assert client.post("/api/v1/internal/accounts/missing/debit", headers=headers, json={"amount": 1, "transactionId": "TX"}).status_code == 404
    assert client.post("/api/v1/internal/accounts/1000000000/debit", headers=headers, json={"amount": 1, "transactionId": "TX"}).status_code == 409
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": 999999999, "transactionId": "TX"}).status_code == 409
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": 0, "transactionId": "TX"}).status_code == 422
    assert client.post("/api/v1/internal/accounts/1012345678/debit", json={"amount": 1, "transactionId": "TX"}).status_code == 401


def test_concurrent_debits_allow_only_one_success(client):
    headers = {"X-Internal-API-Key": "test-internal-key"}

    def debit_once():
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(
                "/api/v1/internal/accounts/1012345678/debit",
                headers=headers,
                json={"amount": 8000000, "transactionId": "CONCURRENT"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: debit_once(), range(2)))

    assert sorted(statuses) == [200, 409]
    db = SessionLocal()
    account = db.get(Account, "1012345678")
    assert account.balance == Decimal("7000000")
    db.close()
