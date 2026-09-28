import secrets
import smtplib
from datetime import datetime, timedelta
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
from backend.payment_service.services.email_service import send_otp_email


class PaymentService:
    def request_otp(self, db_session, transaction_id, access_token):
        try:
            user_response = requests.get(
                f"{USER_SERVICE_URL}/api/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User Service is unavailable",
            ) from exc

        if user_response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to retrieve the account email from User Service",
            )
        email = user_response.json().get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="User Service response is missing an email address",
            )

        otp_code = None
        for _ in range(20):
            candidate = f"{secrets.randbelow(1_000_000):06d}"
            if not OtpModel.is_active_code(db_session, candidate):
                otp_code = candidate
                break
        if otp_code is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to generate a unique active OTP",
            )

        expires_at = datetime.now() + timedelta(minutes=5)
        otp_id = OtpModel.create(db_session, transaction_id, otp_code, expires_at)
        try:
            send_otp_email(email, transaction_id, otp_code, expires_at)
        except (OSError, RuntimeError, smtplib.SMTPException) as exc:
            OtpModel.mark_as_used(db_session, otp_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to send OTP email",
            ) from exc

        return {"message": "OTP sent to the registered email address", "expires_in_seconds": 300}

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
            return {"success": False, "message": "OTP is invalid, expired, or already used"}

        OtpModel.mark_as_used(db_session, otp_record.otp_id)
        return {"success": True, "message": "OTP verified; payment has not been processed"}
