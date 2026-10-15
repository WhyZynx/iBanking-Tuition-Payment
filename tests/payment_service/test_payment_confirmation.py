import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.payment_service.config import JWT_ALGORITHM, JWT_SECRET_KEY
from backend.payment_service.controllers import paymentController
from backend.payment_service.database import get_db
from backend.payment_service.main import app
from backend.payment_service.models import otpModel, transactionModel
from backend.payment_service.services import paymentService


USER_ID = 42
TRANSACTION_ID = "8b7c0d5e-0000-4000-8000-000000000001"
STUDENT_ID = "SV001"
ACCOUNT_NUMBER = "1012345678"
OTP_CODE = "004821"
INTERNAL_KEY = "test-internal-key"


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.statements = []
        self.commits = 0

    def execute(self, query, parameters=None):
        self.statements.append((str(query), parameters))
        return SimpleNamespace(rowcount=1)

    def commit(self):
        self.commits += 1

    def close(self):
        pass


@pytest.fixture
def payment_client(monkeypatch):
    session = FakeSession()
    transaction = SimpleNamespace(
        transaction_id=TRANSACTION_ID,
        payer_user_id=USER_ID,
        source_account_number=ACCOUNT_NUMBER,
        student_id=STUDENT_ID,
        student_name="Nguyen Van B",
        amount=Decimal("4500000.00"),
        status="PENDING",
        completed_at=None,
    )
    state = {
        "tuition": FakeResponse(200, {
            "student_id": STUDENT_ID,
            "student_name": "Nguyen Van B",
            "amount": "5000000.25",
            "status": "UNPAID",
        }),
        "account": FakeResponse(200, {
            "accountNumber": ACCOUNT_NUMBER,
            "userId": USER_ID,
            "balance": 9000000.0,
            "status": "ACTIVE",
        }),
        "debit": FakeResponse(200, {"success": True}),
        "tuition_pay": FakeResponse(200, {"status": "PAID"}),
        "tuition_claim": FakeResponse(201, {"student_id": STUDENT_ID, "transaction_id": TRANSACTION_ID}),
        "get_exception_contains": None,
        "get_exception": None,
        "post_exception": None,
        "put_exception": None,
        "otp_code": OTP_CODE,
        "otp_used": False,
    }
    calls = {"get": [], "post": [], "put": [], "delete": []}
    status_updates = []
    transaction_claim_lock = Lock()

    def get(url, **kwargs):
        calls["get"].append((url, kwargs))
        if state["get_exception_contains"] and state["get_exception_contains"] in url:
            raise state["get_exception"]
        if "/api/v1/users/me" in url:
            return FakeResponse(200, {"email": "payer@example.test"})
        if "/api/v1/tuition/" in url:
            return state["tuition"]
        if "/api/v1/internal/accounts/" in url:
            return state["account"]
        raise AssertionError(f"Unexpected GET URL: {url}")

    def post(url, **kwargs):
        calls["post"].append((url, kwargs))
        if "/claim" in url:
            return state["tuition_claim"]
        if state["post_exception"]:
            raise state["post_exception"]
        return state["debit"]

    def put(url, **kwargs):
        calls["put"].append((url, kwargs))
        if state["put_exception"]:
            raise state["put_exception"]
        return state["tuition_pay"]

    def delete(url, **kwargs):
        calls["delete"].append((url, kwargs))
        return FakeResponse(200, {"released": True})

    def find_transaction(_db, transaction_id):
        return transaction if transaction_id == TRANSACTION_ID else None

    def verify_otp(_db, transaction_id, code):
        if (
            transaction_id == TRANSACTION_ID
            and code == state["otp_code"]
            and not state["otp_used"]
        ):
            return SimpleNamespace(otp_id=1)
        return None

    def mark_otp_used(_db, _otp_id):
        state["otp_used"] = True
        return True

    def complete_transaction(_db, transaction_id, amount):
        if transaction_id != TRANSACTION_ID or transaction.status != "PROCESSING":
            return None
        transaction.amount = amount
        transaction.status = "SUCCESS"
        transaction.completed_at = datetime.now()
        status_updates.append("SUCCESS")
        return transaction.completed_at

    def update_transaction_status(_db, transaction_id, new_status):
        if transaction_id != TRANSACTION_ID or transaction.status != "PROCESSING":
            return False
        transaction.status = new_status
        transaction.completed_at = datetime.now()
        status_updates.append(new_status)
        return True

    def mark_reconciliation_required(_db, transaction_id):
        if transaction_id != TRANSACTION_ID or transaction.status != "PROCESSING":
            return False
        transaction.status = "RECONCILIATION_REQUIRED"
        status_updates.append("RECONCILIATION_REQUIRED")
        return True

    def claim_transaction(_db, transaction_id, payer_user_id):
        with transaction_claim_lock:
            if (
                transaction_id != TRANSACTION_ID
                or payer_user_id != transaction.payer_user_id
                or transaction.status != "PENDING"
            ):
                return False
            transaction.status = "PROCESSING"
            return True

    def release_transaction(_db, transaction_id):
        if transaction_id != TRANSACTION_ID or transaction.status != "PROCESSING":
            return False
        transaction.status = "PENDING"
        return True

    def get_history(_db, user_id):
        if user_id != transaction.payer_user_id:
            return []
        return [{
            "transactionId": transaction.transaction_id,
            "studentId": transaction.student_id,
            "studentName": transaction.student_name,
            "sourceAccountNumber": transaction.source_account_number,
            "amount": transaction.amount,
            "status": transaction.status,
            "createdAt": None,
            "completedAt": transaction.completed_at.isoformat() if transaction.completed_at else None,
        }]

    monkeypatch.setattr(paymentService, "INTERNAL_API_KEY", INTERNAL_KEY)
    monkeypatch.setattr(paymentService.requests, "get", get)
    monkeypatch.setattr(paymentService.requests, "post", post)
    monkeypatch.setattr(paymentService.requests, "put", put)
    monkeypatch.setattr(paymentService.requests, "delete", delete)
    monkeypatch.setattr(paymentService, "send_payment_success_email", lambda **_kwargs: None)
    monkeypatch.setattr(transactionModel.TransactionModel, "find_by_id", find_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "complete", complete_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "update_status", update_transaction_status)
    monkeypatch.setattr(
        transactionModel.TransactionModel,
        "mark_reconciliation_required",
        mark_reconciliation_required,
    )
    monkeypatch.setattr(transactionModel.TransactionModel, "claim_for_processing", claim_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "release_processing", release_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "find_by_user_id", get_history)
    monkeypatch.setattr(otpModel.OtpModel, "verify", verify_otp)
    monkeypatch.setattr(otpModel.OtpModel, "mark_as_used", mark_otp_used)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    token = jwt.encode(
        {"sub": str(USER_ID), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        yield client, transaction, state, calls, status_updates, headers
    app.dependency_overrides.clear()


def confirm(client, headers):
    return client.post(
        "/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": TRANSACTION_ID, "otpCode": OTP_CODE},
    )


def test_successful_payment_revalidates_and_finalizes_transaction(payment_client):
    client, transaction, state, calls, status_updates, headers = payment_client

    response = confirm(client, headers)

    assert response.status_code == 200
    body = response.json()
    assert body["transaction_id"] == TRANSACTION_ID
    assert body["status"] == "SUCCESS"
    assert body["student_id"] == STUDENT_ID
    assert body["student_name"] == "Nguyen Van B"
    assert Decimal(str(body["amount"])) == Decimal("5000000.25")
    assert body["completed_at"]
    assert transaction.status == "SUCCESS"
    assert transaction.amount == Decimal("5000000.25")
    assert transaction.completed_at is not None
    assert state["otp_used"] is True
    assert status_updates == ["SUCCESS"]

    tuition_get, account_get, email_get = calls["get"]
    assert tuition_get[0].endswith(f"/api/v1/tuition/{STUDENT_ID}")
    assert tuition_get[1]["headers"]["X-Internal-API-Key"] == INTERNAL_KEY
    assert account_get[0].endswith(f"/api/v1/internal/accounts/{ACCOUNT_NUMBER}")
    assert account_get[1]["headers"]["X-Internal-API-Key"] == INTERNAL_KEY
    assert email_get[0].endswith("/api/v1/users/me")
    assert email_get[1]["headers"]["Authorization"].startswith("Bearer ")

    claim_url, claim_args = calls["post"][0]
    assert claim_url.endswith(f"/api/v1/tuition/{STUDENT_ID}/claim")
    assert claim_args["json"] == {"transaction_id": TRANSACTION_ID}
    assert claim_args["headers"]["X-Internal-API-Key"] == INTERNAL_KEY

    debit_url, debit_args = calls["post"][1]
    assert debit_url.endswith(f"/api/v1/internal/accounts/{ACCOUNT_NUMBER}/debit")
    assert debit_args["headers"]["X-Internal-API-Key"] == INTERNAL_KEY
    assert Decimal(str(json.loads(debit_args["data"])["amount"])) == Decimal("5000000.25")
    assert json.loads(debit_args["data"])["transactionId"] == TRANSACTION_ID

    tuition_url, tuition_args = calls["put"][0]
    assert tuition_url.endswith(f"/api/v1/tuition/{STUDENT_ID}/pay")
    assert tuition_args["headers"]["X-Internal-API-Key"] == INTERNAL_KEY


@pytest.mark.parametrize("otp_code", ["999999", "expired", "used"])
def test_invalid_otp_returns_400_without_external_side_effects(payment_client, otp_code):
    client, transaction, state, calls, status_updates, headers = payment_client
    state["otp_code"] = "004821" if otp_code != "999999" else "482100"
    state["otp_used"] = otp_code == "used"
    if otp_code == "expired":
        state["otp_used"] = True  # verify() rejects an expired/used record equivalently.

    response = client.post(
        "/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": TRANSACTION_ID, "otpCode": otp_code if otp_code == "999999" else "004821"},
    )

    assert response.status_code == 400
    assert calls["get"] == []
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"
    assert status_updates == []


def test_missing_transaction_returns_404(payment_client):
    client, transaction, _, calls, _, headers = payment_client
    response = client.post(
        "/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": "missing", "otpCode": OTP_CODE},
    )
    assert response.status_code == 404
    assert calls["get"] == []
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"


def test_insufficient_revalidated_balance_leaves_payment_pending(payment_client):
    client, transaction, state, calls, status_updates, headers = payment_client
    state["account"] = FakeResponse(200, {
        "userId": USER_ID,
        "balance": 10.0,
        "status": "ACTIVE",
    })

    response = confirm(client, headers)

    assert response.status_code == 409
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"
    assert state["otp_used"] is False
    assert status_updates == []


def test_paid_tuition_is_rejected_before_debit(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    state["tuition"] = FakeResponse(200, {
        "student_id": STUDENT_ID,
        "student_name": "Nguyen Van B",
        "amount": "5000000.25",
        "status": "PAID",
    })

    response = confirm(client, headers)

    assert response.status_code == 409
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"


def test_missing_tuition_is_rejected_before_debit(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    state["tuition"] = FakeResponse(404)

    response = confirm(client, headers)

    assert response.status_code == 404
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"


def test_inactive_account_is_rejected_before_debit(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    state["account"] = FakeResponse(200, {
        "userId": USER_ID,
        "balance": 9000000.0,
        "status": "INACTIVE",
    })

    response = confirm(client, headers)

    assert response.status_code == 409
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"


def test_missing_account_is_rejected_before_debit(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    state["account"] = FakeResponse(404)

    response = confirm(client, headers)

    assert response.status_code == 404
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"


def test_account_owned_by_another_user_is_rejected(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    state["account"] = FakeResponse(200, {
        "userId": USER_ID + 1,
        "balance": 9000000.0,
        "status": "ACTIVE",
    })

    response = confirm(client, headers)

    assert response.status_code == 403
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"


def test_transaction_already_successful_cannot_be_charged_again(payment_client):
    client, transaction, _, calls, _, headers = payment_client
    transaction.status = "SUCCESS"

    response = confirm(client, headers)

    assert response.status_code == 409
    assert calls["get"] == []
    assert calls["post"] == []
    assert calls["put"] == []


def test_same_transaction_confirmed_concurrently_is_debited_once(payment_client):
    client, transaction, state, calls, status_updates, headers = payment_client

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: confirm(client, headers), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert transaction.status == "SUCCESS"
    debit_calls = [call for call in calls["post"] if "/debit" in call[0]]
    assert len(debit_calls) == 1
    assert len(calls["put"]) == 1
    assert state["otp_used"] is True
    assert status_updates == ["SUCCESS"]


def test_debit_conflict_does_not_update_tuition_or_consume_otp(payment_client):
    client, transaction, state, calls, status_updates, headers = payment_client
    state["debit"] = FakeResponse(409, {"detail": "Insufficient available balance"})

    response = confirm(client, headers)

    assert response.status_code == 409
    assert calls["post"]
    assert calls["put"] == []
    assert calls["delete"]
    assert transaction.status == "FAILED"
    assert state["otp_used"] is True
    assert status_updates == ["FAILED"]


def test_debit_not_found_does_not_update_tuition(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    state["debit"] = FakeResponse(404)

    response = confirm(client, headers)

    assert response.status_code == 404
    assert calls["put"] == []
    assert calls["delete"]
    assert transaction.status == "FAILED"
    assert state["otp_used"] is True


def test_unknown_debit_result_marks_transaction_for_reconciliation(payment_client):
    import requests

    client, transaction, state, calls, status_updates, headers = payment_client
    state["post_exception"] = requests.Timeout("debit response timed out")

    response = confirm(client, headers)

    assert response.status_code == 503
    assert calls["post"]
    assert calls["put"] == []
    assert transaction.status == "RECONCILIATION_REQUIRED"
    assert status_updates == ["RECONCILIATION_REQUIRED"]
    assert "outcome is unknown" in response.json()["detail"]


def test_tuition_failure_after_debit_marks_failed_and_logs_partial_payment(payment_client, caplog):
    client, transaction, state, calls, status_updates, headers = payment_client
    state["tuition_pay"] = FakeResponse(500)

    response = confirm(client, headers)

    assert response.status_code == 502
    assert calls["post"]
    assert calls["put"]
    assert transaction.status == "RECONCILIATION_REQUIRED"
    assert transaction.completed_at is None
    assert state["otp_used"] is True
    assert status_updates == ["RECONCILIATION_REQUIRED"]
    assert "Partial payment: debit succeeded" in caplog.text
    assert "requires reconciliation" in response.json()["detail"]


def test_tuition_timeout_after_debit_marks_failed(payment_client):
    client, transaction, state, calls, status_updates, headers = payment_client
    import requests

    state["put_exception"] = requests.Timeout("tuition timeout")

    response = confirm(client, headers)

    assert response.status_code == 503
    assert calls["post"]
    assert transaction.status == "RECONCILIATION_REQUIRED"
    assert state["otp_used"] is True
    assert status_updates == ["RECONCILIATION_REQUIRED"]


def test_user_service_unavailable_during_revalidation_does_not_debit(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    import requests

    state["get_exception_contains"] = "/api/v1/internal/accounts/"
    state["get_exception"] = requests.ConnectionError("user service unavailable")

    response = confirm(client, headers)

    assert response.status_code == 503
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"
    assert state["otp_used"] is False


def test_tuition_service_unavailable_during_revalidation_does_not_debit(payment_client):
    client, transaction, state, calls, _, headers = payment_client
    import requests

    state["get_exception_contains"] = "/api/v1/tuition/"
    state["get_exception"] = requests.ConnectionError("tuition service unavailable")

    response = confirm(client, headers)

    assert response.status_code == 503
    assert calls["post"] == []
    assert calls["put"] == []
    assert transaction.status == "PENDING"
    assert state["otp_used"] is False


def test_history_contains_successful_transaction(payment_client):
    client, transaction, _, _, _, headers = payment_client
    transaction.status = "SUCCESS"
    transaction.completed_at = datetime.now()

    response = client.get("/api/v1/transactions/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["transactionId"] == TRANSACTION_ID
    assert response.json()["items"][0]["status"] == "SUCCESS"
    assert response.json()["items"][0]["sourceAccountNumber"] == ACCOUNT_NUMBER
    assert response.json()["items"][0]["completedAt"] == transaction.completed_at.isoformat()
