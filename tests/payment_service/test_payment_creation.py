from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.payment_service.config import JWT_ALGORITHM, JWT_SECRET_KEY
from backend.payment_service.database import get_db
from backend.payment_service.main import app
from backend.payment_service.services import paymentService


PAYER_USER_ID = 42
STUDENT_ID = "SV001"
ACCOUNT_NUMBER = "1012345678"
INTERNAL_KEY = "test-internal-key"
TUITION = {
    "student_id": STUDENT_ID,
    "student_name": "Nguyen Van B",
    "amount": "5000000.25",
    "status": "UNPAID",
}
ACCOUNT = {
    "accountNumber": ACCOUNT_NUMBER,
    "userId": PAYER_USER_ID,
    "balance": 9000000.0,
    "status": "ACTIVE",
}


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeResult:
    def __init__(self, row=None, rowcount=0):
        self.row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self.row


class FakeSession:
    def __init__(self, pending=None):
        self.pending = pending
        self.statements = []
        self.commits = 0

    def execute(self, query, parameters=None):
        self.statements.append((str(query), parameters))
        if "SELECT transaction_id" in str(query):
            return FakeResult(self.pending)
        return FakeResult()

    def commit(self):
        self.commits += 1

    def close(self):
        pass


@pytest.fixture
def setup_client(monkeypatch):
    session = FakeSession()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(paymentService, "INTERNAL_API_KEY", INTERNAL_KEY)
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def auth_headers():
    token = jwt.encode(
        {
            "sub": str(PAYER_USER_ID),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def request_payment(client, body=None, authenticated=True):
    headers = auth_headers() if authenticated else {}
    return client.post(
        "/api/v1/payments",
        headers=headers,
        json=body or {"student_id": STUDENT_ID, "account_number": ACCOUNT_NUMBER},
    )


def mock_service_responses(monkeypatch, account=ACCOUNT, account_status=200,
                           tuition=TUITION, tuition_status=200):
    responses = iter([
        FakeResponse(account_status, account),
        FakeResponse(tuition_status, tuition),
    ])
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return next(responses)

    monkeypatch.setattr(paymentService.requests, "get", get)
    return calls


def test_payment_creation_persists_pending_transaction_with_authoritative_amount(
    setup_client, monkeypatch
):
    client, session = setup_client
    calls = mock_service_responses(monkeypatch)

    response = request_payment(client, {
        "student_id": STUDENT_ID,
        "account_number": ACCOUNT_NUMBER,
    })

    assert response.status_code == 201
    body = response.json()
    assert len(body["transaction_id"]) == 36
    assert body["payer_user_id"] == PAYER_USER_ID
    assert body["payer_account_number"] == ACCOUNT_NUMBER
    assert body["student_id"] == STUDENT_ID
    assert body["student_name"] == "Nguyen Van B"
    assert Decimal(str(body["amount"])) == Decimal("5000000.25")
    assert body["status"] == "PENDING"
    assert session.commits == 2

    insert_query, inserted = session.statements[-1]
    assert "'PENDING'" in insert_query
    assert inserted["amount"] == Decimal("5000000.25")
    assert inserted["student_name"] == "Nguyen Van B"
    assert calls[0][1]["headers"] == {"X-Internal-API-Key": INTERNAL_KEY}
    assert calls[1][1]["headers"] == {"X-Internal-API-Key": INTERNAL_KEY}
    assert calls[1][0].endswith(f"/api/v1/tuition/{STUDENT_ID}")


def test_payment_creation_requires_jwt(setup_client, monkeypatch):
    client, _ = setup_client
    response = request_payment(client, authenticated=False)
    assert response.status_code == 401


def test_payment_creation_account_not_found(setup_client, monkeypatch):
    client, _ = setup_client
    mock_service_responses(monkeypatch, account_status=404)
    assert request_payment(client).status_code == 404


def test_payment_creation_rejects_account_owned_by_another_user(setup_client, monkeypatch):
    client, _ = setup_client
    mock_service_responses(monkeypatch, account={**ACCOUNT, "userId": 99})
    assert request_payment(client).status_code == 403


def test_payment_creation_rejects_inactive_account(setup_client, monkeypatch):
    client, _ = setup_client
    mock_service_responses(monkeypatch, account={**ACCOUNT, "status": "INACTIVE"})
    assert request_payment(client).status_code == 409


def test_payment_creation_tuition_not_found(setup_client, monkeypatch):
    client, _ = setup_client
    mock_service_responses(monkeypatch, tuition_status=404)
    assert request_payment(client).status_code == 404


def test_payment_creation_rejects_paid_tuition(setup_client, monkeypatch):
    client, _ = setup_client
    mock_service_responses(monkeypatch, tuition={**TUITION, "status": "PAID"})
    assert request_payment(client).status_code == 409


def test_payment_creation_rejects_insufficient_balance(setup_client, monkeypatch):
    client, _ = setup_client
    mock_service_responses(monkeypatch, account={**ACCOUNT, "balance": 100.0})
    assert request_payment(client).status_code == 409


def test_payment_creation_rejects_frontend_amount_instead_of_using_it(setup_client):
    client, _ = setup_client
    response = request_payment(client, {
        "student_id": STUDENT_ID,
        "account_number": ACCOUNT_NUMBER,
        "amount": 1,
    })
    assert response.status_code == 422


def test_payment_creation_rejects_duplicate_pending_transaction(setup_client, monkeypatch):
    client, session = setup_client
    session.pending = ("existing-transaction",)
    mock_service_responses(monkeypatch)
    response = request_payment(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "A pending payment already exists for this student."
    assert session.commits == 1
