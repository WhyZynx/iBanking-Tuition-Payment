import json
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from uuid import uuid4

import requests
from fastapi import HTTPException, status

from backend.payment_service.config import (
    INTERNAL_API_KEY,
    TUITION_SERVICE_URL,
    USER_SERVICE_URL,
)
from backend.payment_service.models.otpModel import OtpModel
from backend.payment_service.models.transactionModel import TransactionModel


class PaymentService:
    def create_payment(self, db_session, payer_user_id, student_id, account_number):
        headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
        try:
            account_response = requests.get(
                f"{USER_SERVICE_URL}/api/v1/internal/accounts/{quote(account_number, safe='')}",
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User Service is unavailable",
            ) from exc

        if account_response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=404, detail="Account not found")
        if account_response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="User Service could not validate the account",
            )

        account = account_response.json()
        account_owner_id = account.get("user_id", account.get("userId"))
        try:
            owns_account = account_owner_id is not None and int(account_owner_id) == payer_user_id
        except (TypeError, ValueError):
            owns_account = False
        if not owns_account:
            raise HTTPException(status_code=403, detail="Account does not belong to the authenticated user")
        if account.get("status") != "ACTIVE":
            raise HTTPException(status_code=409, detail="Account is inactive")

        try:
            tuition_response = requests.get(
                f"{TUITION_SERVICE_URL}/api/v1/tuition/{quote(student_id, safe='')}",
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tuition Service is unavailable",
            ) from exc

        if tuition_response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=404, detail="Tuition information not found")
        if tuition_response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tuition Service could not look up the student",
            )

        tuition = tuition_response.json()
        if tuition.get("status") == "PAID":
            raise HTTPException(status_code=409, detail="Tuition has already been paid")
        if tuition.get("status") != "UNPAID":
            raise HTTPException(status_code=502, detail="Tuition Service returned an unsupported status")

        try:
            amount = Decimal(str(tuition["amount"]))
            balance = Decimal(str(account["balance"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="A service returned invalid account or tuition data",
            ) from exc
        if not amount.is_finite() or amount <= 0 or not balance.is_finite():
            raise HTTPException(status_code=502, detail="A service returned invalid account or tuition data")
        if balance < amount:
            raise HTTPException(status_code=409, detail="Insufficient account balance")

        student_id = tuition.get("student_id", student_id)
        student_name = tuition.get("student_name")
        if not student_name:
            raise HTTPException(status_code=502, detail="Tuition Service response is missing student name")

        pending = TransactionModel.find_pending_by_user_and_student(
            db_session,
            payer_user_id,
            student_id,
        )
        if pending is not None:
            raise HTTPException(
                status_code=409,
                detail="A pending payment already exists for this student.",
            )

        transaction_id = str(uuid4())
        TransactionModel.create(
            db_session=db_session,
            transaction_id=transaction_id,
            payer_user_id=payer_user_id,
            source_account_number=account_number,
            student_id=student_id,
            student_name=student_name,
            amount=amount,
        )
        return {
            "transaction_id": transaction_id,
            "payer_user_id": payer_user_id,
            "payer_account_number": account_number,
            "student_id": student_id,
            "student_name": student_name,
            "amount": amount,
            "status": "PENDING",
        }

    def confirm_payment(self, db_session, transaction_id, otp_code):
        otp_record = OtpModel.verify(db_session, transaction_id, otp_code)
        if not otp_record:
            return {"success": False, "message": "MĂ£ OTP sai hoáº·c Ä‘Ă£ háº¿t háº¡n!"}

        transaction = TransactionModel.find_by_id(db_session, transaction_id)
        user_service_url = (
            f"{USER_SERVICE_URL}/api/v1/internal/accounts/"
            f"{transaction.source_account_number}/debit"
        )
        headers = {"X-Internal-API-Key": INTERNAL_API_KEY, "Content-Type": "application/json"}
        payload = (
            f'{{"amount":{transaction.amount},'
            f'"transactionId":{json.dumps(transaction_id)}}}'
        )
        response = requests.post(user_service_url, data=payload, headers=headers)

        if response.status_code == 200:
            TransactionModel.update_status(db_session, transaction_id, "SUCCESS")
            OtpModel.mark_as_used(db_session, otp_record.otp_id)
            return {"success": True, "message": "Thanh toĂ¡n thĂ nh cĂ´ng!"}

        TransactionModel.update_status(db_session, transaction_id, "FAILED")
        return {"success": False, "message": "Sá»‘ dÆ° khĂ´ng Ä‘á»§ hoáº·c lá»—i tĂ i khoáº£n!"}
