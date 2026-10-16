from datetime import datetime, timedelta, timezone
import smtplib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.payment_service.config import JWT_ALGORITHM, JWT_SECRET_KEY
from backend.payment_service.controllers import paymentController
from backend.payment_service.database import get_db
from backend.payment_service.main import app
from backend.payment_service.models import otpModel
from backend.payment_service.services import email_service, paymentService


USER_ID = 42
TRANSACTION_ID = "8b7c0d5e-0000-4000-8000-000000000001"


class OtpSession:
    def close(self):
        pass


class FakeEmailResponse:
    status_code = 200

    @staticmethod
    def json():
        return {"email": "payer@example.com"}


class FakeEmailResponseWithTuitionStatus:
    status_code = 200

    def __init__(self, tuition_status):
        self.tuition_status = tuition_status

    def json(self):
        return {
            "student_id": "SV001",
            "student_name": "Student",
            "amount": "500.00",
            "status": self.tuition_status,
        }


@pytest.fixture
def otp_client(monkeypatch):
    session = OtpSession()
    transaction = SimpleNamespace(
        transaction_id=TRANSACTION_ID,
        payer_user_id=USER_ID,
        source_account_number="1012345678",
        student_id="SV001",
        student_name="Student",
        amount=500.00,
        status="PENDING",
    )
    records = []
    sent_emails = []
    next_id = 1

    def find_transaction(_session, transaction_id):
        return transaction if transaction_id == TRANSACTION_ID else None

    def claim_transaction(_session, transaction_id, payer_user_id):
        if (
            transaction_id != TRANSACTION_ID
            or payer_user_id != USER_ID
            or transaction.status != "PENDING"
        ):
            return False
        transaction.status = "PROCESSING"
        return True

    def release_transaction(_session, transaction_id):
        if transaction_id != TRANSACTION_ID or transaction.status != "PROCESSING":
            return False
        transaction.status = "PENDING"
        return True

    def is_active_code(_session, code):
        now = datetime.now()
        return any(
            record["code"] == code
            and not record["used"]
            and record["expires_at"] > now
            for record in records
        )

    def create_otp(_session, transaction_id, code, expires_at):
        nonlocal next_id
        for record in records:
            if record["transaction_id"] == transaction_id and not record["used"]:
                record["used"] = True
        otp_id = next_id
        next_id += 1
        records.append({
            "id": otp_id,
            "transaction_id": transaction_id,
            "code": code,
            "expires_at": expires_at,
            "used": True,
        })
        return otp_id

    def activate_otp(_session, otp_id, transaction_id):
        for record in records:
            if record["transaction_id"] == transaction_id and record["id"] != otp_id:
                record["used"] = True
            elif record["id"] == otp_id and record["expires_at"] > datetime.now():
                record["used"] = False
                return True
        return False

    def verify_otp(_session, transaction_id, code):
        now = datetime.now()
        for record in records:
            if (
                record["transaction_id"] == transaction_id
                and record["code"] == code
                and not record["used"]
                and record["expires_at"] > now
            ):
                return SimpleNamespace(otp_id=record["id"])
        return None

    def mark_used(_session, otp_id):
        for record in records:
            if record["id"] == otp_id:
                record["used"] = True
                return True
        return False

    monkeypatch.setattr(paymentController.TransactionModel, "find_by_id", find_transaction)
    monkeypatch.setattr(paymentController.TransactionModel, "claim_for_processing", claim_transaction)
    monkeypatch.setattr(paymentController.TransactionModel, "release_processing", release_transaction)
    monkeypatch.setattr(otpModel.OtpModel, "is_active_code", is_active_code)
    monkeypatch.setattr(otpModel.OtpModel, "create", create_otp)
    monkeypatch.setattr(otpModel.OtpModel, "activate", activate_otp)
    monkeypatch.setattr(otpModel.OtpModel, "verify", verify_otp)
    monkeypatch.setattr(otpModel.OtpModel, "mark_as_used", mark_used)
    monkeypatch.setattr(paymentService.requests, "get", lambda *args, **kwargs: FakeEmailResponse())
    monkeypatch.setattr(paymentService, "send_otp_email", lambda *args: sent_emails.append(args))
    random_values = iter([4821, 4821, 874533, 9123])
    monkeypatch.setattr(
        paymentService.secrets,
        "randbelow",
        lambda upper_bound: next(random_values),
    )

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
        yield client, transaction, records, sent_emails, headers
    app.dependency_overrides.clear()


def test_request_otp_creates_six_digit_code_and_keeps_transaction_pending(otp_client):
    client, transaction, records, sent_emails, headers = otp_client

    response = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)

    assert response.status_code == 200
    assert response.json()["expires_in_seconds"] == 300
    assert len(records) == 1
    assert records[0]["code"] == "004821"
    assert len(records[0]["code"]) == 6
    assert records[0]["used"] is False
    assert timedelta(minutes=4, seconds=59) <= records[0]["expires_at"] - datetime.now() <= timedelta(minutes=5)
    assert sent_emails[0][0] == "payer@example.com"
    assert sent_emails[0][1] == TRANSACTION_ID
    assert transaction.status == "PENDING"


def test_request_otp_transaction_not_found(otp_client):
    client, _, _, _, headers = otp_client
    response = client.post("/api/v1/payments/missing/otp", headers=headers)
    assert response.status_code == 404


def test_request_otp_requires_jwt(otp_client):
    client, _, _, _, _ = otp_client
    response = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp")
    assert response.status_code == 401


def test_request_otp_rejects_transaction_owned_by_another_user(otp_client):
    client, transaction, _, _, headers = otp_client
    transaction.payer_user_id = 999
    response = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)
    assert response.status_code == 403


def test_request_otp_rejects_non_pending_transaction(otp_client):
    client, transaction, _, _, headers = otp_client
    transaction.status = "FAILED"
    response = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)
    assert response.status_code == 409


def test_requesting_otp_again_invalidates_the_previous_code(otp_client):
    client, _, records, _, headers = otp_client

    first = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)
    second = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)

    assert first.status_code == second.status_code == 200
    assert len(records) == 2
    assert records[0]["used"] is True
    assert records[1]["used"] is False
    assert records[0]["code"] != records[1]["code"]

    old_confirm = client.post(
        "/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": TRANSACTION_ID, "otpCode": records[0]["code"]},
    )
    assert old_confirm.status_code == 400
    assert records[1]["used"] is False


@pytest.mark.parametrize(
    "smtp_error",
    [
        TimeoutError("SMTP_PASSWORD=do-not-log"),
        smtplib.SMTPAuthenticationError(535, b"SMTP_PASSWORD=do-not-log"),
        RuntimeError("SMTP_PASSWORD=do-not-log"),
    ],
)
def test_otp_smtp_failure_returns_error_and_leaves_code_inactive(
    otp_client, monkeypatch, caplog, smtp_error
):
    client, transaction, records, sent_emails, headers = otp_client
    monkeypatch.setattr(
        paymentService,
        "send_otp_email",
        Mock(side_effect=smtp_error),
    )

    response = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)

    assert response.status_code == 502
    assert "SMTP_PASSWORD" not in response.text
    assert "do-not-log" not in response.text
    assert "SMTP_PASSWORD" not in caplog.text
    assert "do-not-log" not in caplog.text
    assert len(records) == 1
    assert records[0]["used"] is True
    assert otpModel.OtpModel.verify(None, TRANSACTION_ID, records[0]["code"]) is None
    assert sent_emails == []
    assert transaction.status == "PENDING"


def test_otp_is_not_reported_successful_if_activation_fails(otp_client, monkeypatch, caplog):
    client, transaction, records, sent_emails, headers = otp_client
    monkeypatch.setattr(
        otpModel.OtpModel,
        "activate",
        Mock(side_effect=RuntimeError("SMTP_PASSWORD=do-not-log")),
    )

    response = client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)

    assert response.status_code == 503
    assert "SMTP_PASSWORD" not in response.text
    assert "do-not-log" not in response.text
    assert "SMTP_PASSWORD" not in caplog.text
    assert "do-not-log" not in caplog.text
    assert sent_emails
    assert records[0]["used"] is True
    assert otpModel.OtpModel.verify(None, TRANSACTION_ID, records[0]["code"]) is None
    assert transaction.status == "PENDING"


@pytest.mark.parametrize("invalid_kind", ["expired", "wrong", "used"])
def test_confirm_rejects_expired_wrong_or_used_otp_without_payment_actions(
    otp_client, monkeypatch, invalid_kind
):
    client, transaction, records, _, headers = otp_client
    records.append({
        "id": 1,
        "transaction_id": TRANSACTION_ID,
        "code": "729481" if invalid_kind != "wrong" else "654321",
        "expires_at": (
            datetime.now() - timedelta(seconds=1)
            if invalid_kind == "expired"
            else datetime.now() + timedelta(minutes=5)
        ),
        "used": invalid_kind == "used",
    })
    debit = Mock(side_effect=AssertionError("OTP verification must not debit an account"))
    monkeypatch.setattr(paymentService.requests, "post", debit)
    update_status = Mock(side_effect=AssertionError("OTP verification must not change transaction status"))
    monkeypatch.setattr(paymentController.TransactionModel, "update_status", update_status)

    response = client.post(
        "/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": TRANSACTION_ID, "otpCode": "729481"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "OTP is invalid, expired, or already used"
    assert transaction.status == "PENDING"
    debit.assert_not_called()
    update_status.assert_not_called()


def test_paid_tuition_ends_transaction_and_consumes_otp_without_debit(otp_client, monkeypatch):
    client, transaction, records, _, headers = otp_client
    client.post(f"/api/v1/payments/{TRANSACTION_ID}/otp", headers=headers)
    otp_code = records[0]["code"]
    debit = Mock(side_effect=AssertionError("STEP 5 must not debit accounts"))
    monkeypatch.setattr(paymentService.requests, "post", debit)
    def fail_transaction(_session, transaction_id, new_status):
        assert transaction_id == TRANSACTION_ID
        assert transaction.status == "PROCESSING"
        transaction.status = new_status
        return True

    update_status = Mock(side_effect=fail_transaction)
    monkeypatch.setattr(paymentController.TransactionModel, "update_status", update_status)
    monkeypatch.setattr(
        paymentService.requests,
        "get",
        lambda *args, **kwargs: FakeEmailResponseWithTuitionStatus("PAID"),
    )

    response = client.post(
        "/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": TRANSACTION_ID, "otpCode": otp_code},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Tuition has already been paid"
    assert records[0]["used"] is True
    assert transaction.status == "FAILED"
    debit.assert_not_called()
    update_status.assert_called_once()
    assert update_status.call_args.args[1:] == (TRANSACTION_ID, "FAILED")


def test_otp_verification_query_requires_unused_matching_unexpired_code():
    captured = {}

    class Result:
        @staticmethod
        def fetchone():
            return None

    class Session:
        @staticmethod
        def execute(query, params):
            captured["query"] = str(query)
            captured["params"] = params
            return Result()

    assert otpModel.OtpModel.verify(Session(), TRANSACTION_ID, "004821") is None
    assert "otp_code = :code" in captured["query"]
    assert "is_used = FALSE" in captured["query"]
    assert "expires_at > CURRENT_TIMESTAMP" in captured["query"]
    assert captured["params"] == {"id": TRANSACTION_ID, "code": "004821"}


def test_email_helper_builds_expected_message(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr(email_service, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(email_service, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service, "SMTP_USERNAME", "sender@example.test")
    monkeypatch.setattr(email_service, "SMTP_PASSWORD", "placeholder")
    monkeypatch.setattr(email_service, "SMTP_FROM_EMAIL", "sender@example.test")
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: FakeSMTP())

    expiry = datetime.now() + timedelta(minutes=5)
    email_service.send_otp_email("payer@example.com", TRANSACTION_ID, "004821", expiry)

    message = sent["message"]
    assert message["Subject"] == "iBanking - OTP Verification"
    assert message["To"] == "payer@example.com"
    assert "004821" in message.get_content()
    assert TRANSACTION_ID in message.get_content()
    assert "5 minutes" in message.get_content()
    assert sent["login"] == ("sender@example.test", "placeholder")
