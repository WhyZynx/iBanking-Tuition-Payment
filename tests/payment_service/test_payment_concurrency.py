import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from types import SimpleNamespace

from fastapi import HTTPException

from backend.payment_service.models import otpModel, transactionModel
from backend.payment_service.services import paymentService
from backend.payment_service.services.paymentService import PaymentService


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


def test_two_payers_confirming_same_student_only_one_is_debited(monkeypatch):
    transactions = {
        f"tx-{user_id}": SimpleNamespace(
            transaction_id=f"tx-{user_id}",
            payer_user_id=user_id,
            source_account_number=f"account-{user_id}",
            student_id="SV001",
            student_name="Student",
            amount=Decimal("5000000.00"),
            status="PENDING",
        )
        for user_id in (1, 2)
    }
    transaction_lock = Lock()
    tuition_lock = Lock()
    state = {
        "tuition_claim": None,
        "tuition_paid": False,
        "claim_count": 0,
        "debits": [],
        "successes": [],
        "balances": {1: Decimal("9000000.00"), 2: Decimal("9000000.00")},
    }

    def find_transaction(_db, transaction_id):
        return transactions.get(transaction_id)

    def claim_transaction(_db, transaction_id, payer_user_id):
        with transaction_lock:
            transaction = transactions[transaction_id]
            if transaction.status != "PENDING" or transaction.payer_user_id != payer_user_id:
                return False
            transaction.status = "PROCESSING"
            return True

    def release_transaction(_db, transaction_id):
        with transaction_lock:
            transaction = transactions[transaction_id]
            if transaction.status != "PROCESSING":
                return False
            transaction.status = "PENDING"
            return True

    def complete_transaction(_db, transaction_id, amount):
        transaction = transactions[transaction_id]
        if transaction.status != "PROCESSING":
            return None
        transaction.status = "SUCCESS"
        transaction.amount = amount
        state["successes"].append(transaction_id)
        return datetime.now(timezone.utc)

    def update_transaction(_db, transaction_id, new_status):
        transactions[transaction_id].status = new_status
        return True

    def verify_otp(_db, transaction_id, _code):
        return SimpleNamespace(otp_id=transaction_id)

    def consume_otp(_db, _otp_id):
        return True

    def get(url, **_kwargs):
        if "/api/v1/tuition/" in url:
            return FakeResponse(200, {
                "student_id": "SV001",
                "student_name": "Student",
                "amount": "5000000.00",
                "status": "PAID" if state["tuition_paid"] else "UNPAID",
            })
        if "/api/v1/users/me" in url:
            return FakeResponse(200, {"email": "payer@example.test"})
        user_id = int(url.rsplit("account-", 1)[1])
        return FakeResponse(200, {
            "userId": user_id,
            "balance": str(state["balances"][user_id]),
            "status": "ACTIVE",
        })

    def post(url, **_kwargs):
        if url.endswith("/claim"):
            transaction_id = _kwargs["json"]["transaction_id"]
            with tuition_lock:
                if state["tuition_claim"] is not None or state["tuition_paid"]:
                    return FakeResponse(409)
                state["tuition_claim"] = transaction_id
                state["claim_count"] += 1
                return FakeResponse(201)
        transaction_id = json.loads(_kwargs["data"])["transactionId"]
        state["debits"].append(transaction_id)
        payer_user_id = transactions[transaction_id].payer_user_id
        state["balances"][payer_user_id] -= Decimal(json.loads(_kwargs["data"])["amount"])
        return FakeResponse(200, {"success": True})

    def put(_url, **_kwargs):
        with tuition_lock:
            if state["tuition_paid"]:
                return FakeResponse(409)
            state["tuition_paid"] = True
            return FakeResponse(200, {"status": "PAID"})

    def delete(url, **_kwargs):
        transaction_id = url.rsplit("/", 1)[1]
        with tuition_lock:
            if state["tuition_claim"] == transaction_id:
                state["tuition_claim"] = None
        return FakeResponse(200)

    monkeypatch.setattr(transactionModel.TransactionModel, "find_by_id", find_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "claim_for_processing", claim_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "release_processing", release_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "complete", complete_transaction)
    monkeypatch.setattr(transactionModel.TransactionModel, "update_status", update_transaction)
    monkeypatch.setattr(otpModel.OtpModel, "verify", verify_otp)
    monkeypatch.setattr(otpModel.OtpModel, "mark_as_used", consume_otp)
    monkeypatch.setattr(paymentService, "INTERNAL_API_KEY", "test-key")
    monkeypatch.setattr(paymentService, "send_payment_success_email", lambda **_kwargs: None)
    monkeypatch.setattr(paymentService.requests, "get", get)
    monkeypatch.setattr(paymentService.requests, "post", post)
    monkeypatch.setattr(paymentService.requests, "put", put)
    monkeypatch.setattr(paymentService.requests, "delete", delete)

    service = PaymentService()

    def confirm(transaction_id, user_id):
        try:
            result = service.confirm_payment(
                None, transaction_id, "004821", user_id, "test-access-token"
            )
            return result["status"]
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda args: confirm(*args), [("tx-1", 1), ("tx-2", 2)]))

    assert results.count("SUCCESS") == 1
    assert results.count(409) == 1
    assert len(state["successes"]) == 1
    assert len(state["debits"]) == 1
    assert state["claim_count"] == 1
    assert state["tuition_paid"] is True
    assert sum(transaction.status == "SUCCESS" for transaction in transactions.values()) == 1

    losing_transaction = next(
        transaction for transaction in transactions.values()
        if transaction.status != "SUCCESS"
    )
    if losing_transaction.status == "PENDING":
        loser_result = confirm(losing_transaction.transaction_id, losing_transaction.payer_user_id)
        assert loser_result == 409

    assert losing_transaction.status == "FAILED"
    assert sorted(transaction.status for transaction in transactions.values()) == ["FAILED", "SUCCESS"]
    assert state["claim_count"] == 1
    assert len(state["debits"]) == 1
    assert sorted(state["balances"].values()) == [Decimal("4000000.00"), Decimal("9000000.00")]
