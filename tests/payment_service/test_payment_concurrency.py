from concurrent.futures import ThreadPoolExecutor
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
    state = {"tuition_claim": None, "tuition_paid": False, "debits": [], "successes": []}

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
        return SimpleNamespace(isoformat=lambda: "2026-09-29T12:00:00")

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
        user_id = int(url.rsplit("account-", 1)[1])
        return FakeResponse(200, {
            "userId": user_id,
            "balance": "9000000.00",
            "status": "ACTIVE",
        })

    def post(url, **_kwargs):
        if url.endswith("/claim"):
            transaction_id = _kwargs["json"]["transaction_id"]
            with tuition_lock:
                if state["tuition_claim"] is not None or state["tuition_paid"]:
                    return FakeResponse(409)
                state["tuition_claim"] = transaction_id
                return FakeResponse(201)
        transaction_id = _kwargs["data"].split('"transactionId":"', 1)[1].split('"', 1)[0]
        state["debits"].append(transaction_id)
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
    monkeypatch.setattr(paymentService.requests, "get", get)
    monkeypatch.setattr(paymentService.requests, "post", post)
    monkeypatch.setattr(paymentService.requests, "put", put)
    monkeypatch.setattr(paymentService.requests, "delete", delete)

    service = PaymentService()

    def confirm(transaction_id, user_id):
        try:
            result = service.confirm_payment(None, transaction_id, "004821", user_id)
            return result["status"]
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda args: confirm(*args), [("tx-1", 1), ("tx-2", 2)]))

    assert results.count("SUCCESS") == 1
    assert results.count(409) == 1
    assert len(state["successes"]) == 1
    assert len(state["debits"]) == 1
    assert state["tuition_paid"] is True
    assert sum(transaction.status == "SUCCESS" for transaction in transactions.values()) == 1
    assert sum(transaction.status == "PENDING" for transaction in transactions.values()) == 1
