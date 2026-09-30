import json
import logging
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
from backend.payment_service.services.email_service import (
    send_otp_email,
    send_payment_success_email,
)

logger = logging.getLogger(__name__)


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
        logger.info("OTP generated and stored for transaction %s (otp_id=%s)", transaction_id, otp_id)
        try:
            send_otp_email(email, transaction_id, otp_code, expires_at)
        except smtplib.SMTPAuthenticationError as exc:
            logger.exception("SMTP authentication failed while sending OTP for transaction %s", transaction_id)
            OtpModel.mark_as_used(db_session, otp_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SMTP authentication failed; check the Payment Service SMTP username and password",
            ) from exc
        except (OSError, RuntimeError, smtplib.SMTPException) as exc:
            logger.exception("Could not send OTP email for transaction %s", transaction_id)
            OtpModel.mark_as_used(db_session, otp_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OTP email could not be sent; check Payment Service SMTP configuration and connectivity",
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

    def confirm_payment(self,db_session,transaction_id,otp_code,payer_user_id,access_token,):
        transaction = TransactionModel.find_by_id(db_session, transaction_id)
        if transaction is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        if transaction.payer_user_id != payer_user_id:
            raise HTTPException(status_code=403, detail="Transaction does not belong to the authenticated user")
        if transaction.status != "PENDING":
            raise HTTPException(status_code=409, detail="Transaction is not pending")

        if not TransactionModel.claim_for_processing(db_session, transaction_id, payer_user_id):
            raise HTTPException(status_code=409, detail="Transaction is already being processed")

        try:
            otp_record = OtpModel.verify(db_session, transaction_id, otp_code)
        except Exception:
            TransactionModel.release_processing(db_session, transaction_id)
            raise
        if not otp_record:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=400, detail="OTP is invalid, expired, or already used")

        headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
        student_id = transaction.student_id
        try:
            tuition_response = requests.get(
                f"{TUITION_SERVICE_URL}/api/v1/tuition/{quote(student_id, safe='')}",
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tuition Service is unavailable",
            ) from exc

        if tuition_response.status_code == status.HTTP_404_NOT_FOUND:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=404, detail="Tuition information not found")
        if tuition_response.status_code != status.HTTP_200_OK:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tuition Service could not revalidate the tuition",
            )

        try:
            tuition = tuition_response.json()
        except (ValueError, TypeError) as exc:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="Tuition Service returned invalid data") from exc
        if not isinstance(tuition, dict):
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="Tuition Service returned invalid data")
        if tuition.get("status") == "PAID":
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=409, detail="Tuition has already been paid")
        if tuition.get("status") != "UNPAID":
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="Tuition Service returned an unsupported status")
        try:
            amount = Decimal(str(tuition["amount"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="Tuition Service returned an invalid amount") from exc
        if not amount.is_finite() or amount <= 0:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="Tuition Service returned an invalid amount")

        account_number = transaction.source_account_number
        try:
            account_response = requests.get(
                f"{USER_SERVICE_URL}/api/v1/internal/accounts/{quote(account_number, safe='')}",
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User Service is unavailable",
            ) from exc

        if account_response.status_code == status.HTTP_404_NOT_FOUND:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=404, detail="Account not found")
        if account_response.status_code != status.HTTP_200_OK:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="User Service could not revalidate the account",
            )
        try:
            account = account_response.json()
        except (ValueError, TypeError) as exc:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="User Service returned invalid account data") from exc
        if not isinstance(account, dict):
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=502, detail="User Service returned invalid account data")
        
        account_owner_raw = account.get("userId")
        if account_owner_raw is None:
            account_owner_raw = account.get("user_id")

        try:
            if account_owner_raw is None:
                raise ValueError("Missing account owner ID")

            account_owner_id = int(account_owner_raw)
            balance = Decimal(str(account["balance"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=502,
                detail="User Service returned invalid account data",) from exc
        
        if account_owner_id != payer_user_id:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=403, detail="Account does not belong to the authenticated user")
        if account.get("status") != "ACTIVE":
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=409, detail="Account is inactive")
        if not balance.is_finite() or balance < amount:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=409, detail="Insufficient account balance")

        claim_url = f"{TUITION_SERVICE_URL}/api/v1/tuition/{quote(student_id, safe='')}/claim"
        try:
            claim_response = requests.post(
                claim_url,
                json={"transaction_id": transaction_id},
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            self._release_tuition_claim(student_id, transaction_id, headers)
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tuition Service is unavailable while claiming the tuition",
            ) from exc
        if claim_response.status_code == status.HTTP_404_NOT_FOUND:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=404, detail="Tuition information not found")
        if claim_response.status_code == status.HTTP_409_CONFLICT:
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=409, detail="Tuition has already been claimed or paid")
        if claim_response.status_code != status.HTTP_201_CREATED:
            self._release_tuition_claim(student_id, transaction_id, headers)
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tuition Service could not claim the tuition",
            )
        try:
            otp_consumed = OtpModel.mark_as_used(db_session, otp_record.otp_id)
        except Exception as exc:
            logger.exception("Could not consume OTP for transaction %s", transaction_id)
            self._release_tuition_claim(student_id, transaction_id, headers)
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=503, detail="Could not safely consume OTP") from exc
        if not otp_consumed:
            self._release_tuition_claim(student_id, transaction_id, headers)
            TransactionModel.release_processing(db_session, transaction_id)
            raise HTTPException(status_code=400, detail="OTP is invalid, expired, or already used")

        debit_url = (
            f"{USER_SERVICE_URL}/api/v1/internal/accounts/"
            f"{quote(account_number, safe='')}/debit"
        )
        debit_payload = (
            f'{{"amount":{format(amount, "f")},'
            f'"transactionId":{json.dumps(transaction_id)}}}'
        )
        debit_headers = {**headers, "Content-Type": "application/json"}
        try:
            debit_response = requests.post(
                debit_url,
                data=debit_payload,
                headers=debit_headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            logger.exception(
                "Debit outcome is unknown for transaction %s; transaction requires reconciliation",
                transaction_id,
            )
            self._mark_transaction_failed(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User Service debit outcome is unknown; transaction requires reconciliation",
            ) from exc

        if debit_response.status_code == status.HTTP_404_NOT_FOUND:
            self._release_tuition_claim(student_id, transaction_id, headers)
            self._mark_transaction_failed(db_session, transaction_id)
            raise HTTPException(status_code=404, detail="Account not found")
        if debit_response.status_code == status.HTTP_409_CONFLICT:
            self._release_tuition_claim(student_id, transaction_id, headers)
            self._mark_transaction_failed(db_session, transaction_id)
            raise HTTPException(status_code=409, detail="Account is inactive or has insufficient balance")
        if debit_response.status_code != status.HTTP_200_OK:
            logger.error(
                "User Service returned HTTP %s while debiting transaction %s; transaction requires reconciliation",
                debit_response.status_code,
                transaction_id,
            )
            self._mark_transaction_failed(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="User Service debit failed; transaction requires reconciliation",
            )

        tuition_pay_url = f"{TUITION_SERVICE_URL}/api/v1/tuition/{quote(student_id, safe='')}/pay"
        try:
            tuition_pay_response = requests.put(
                tuition_pay_url,
                headers=headers,
                timeout=5,
            )
        except requests.RequestException as exc:
            logger.exception(
                "Partial payment: debit succeeded but Tuition Service update failed for transaction %s",
                transaction_id,
            )
            self._mark_transaction_failed(db_session, transaction_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Debit succeeded but tuition update failed; transaction requires reconciliation",
            ) from exc

        if tuition_pay_response.status_code != status.HTTP_200_OK:
            logger.error(
                "Partial payment: debit succeeded but Tuition Service returned HTTP %s for transaction %s",
                tuition_pay_response.status_code,
                transaction_id,
            )
            self._mark_transaction_failed(db_session, transaction_id)
            if tuition_pay_response.status_code in (404, 409):
                raise HTTPException(
                    status_code=tuition_pay_response.status_code,
                    detail="Debit succeeded but tuition update failed; transaction requires reconciliation",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Debit succeeded but tuition update failed; transaction requires reconciliation",
            )

        try:
            saved_completed_at = TransactionModel.complete(
                db_session,
                transaction_id,
                amount,
        )
        except Exception as exc:
            logger.exception(
                "Partial payment: debit and tuition update succeeded but transaction finalization failed for %s",
                transaction_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Debit and tuition update succeeded but transaction could not be finalized",
            ) from exc

        if saved_completed_at is None:
            logger.error(
                "Payment side effects succeeded but transaction %s was no longer PENDING during finalization",
                transaction_id,
            )
            raise HTTPException(
                status_code=409,
                detail="Transaction could not be finalized",
            )

        try:
            user_response = requests.get(
                f"{USER_SERVICE_URL}/api/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )

            if user_response.status_code == status.HTTP_200_OK:
                user_data = user_response.json()
                email = user_data.get("email")

                if email:
                    send_payment_success_email(
                        email=email,
                        transaction_id=transaction_id,
                        student_id=tuition.get("student_id", student_id),
                        student_name=tuition.get(
                            "student_name",
                            transaction.student_name,
                        ),
                        amount=amount,
                        account_number=account_number,
                        completed_at=saved_completed_at,
                    )
                else:
                    logger.error(
                        "Payment succeeded but user email is missing for transaction %s",
                        transaction_id,
                    )
            else:
                logger.error(
                    "Payment succeeded but User Service returned HTTP %s while retrieving email for transaction %s",
                    user_response.status_code,
                    transaction_id,
                )

        except Exception:
            logger.exception(
                "Payment succeeded but confirmation email could not be sent for transaction %s",
                transaction_id,
            )

        return {
            "transaction_id": transaction_id,
            "status": "SUCCESS",
            "student_id": tuition.get("student_id", student_id),
            "student_name": tuition.get(
                "student_name",
                transaction.student_name,
            ),
            "amount": amount,
            "completed_at": saved_completed_at.isoformat(),
        }

    @staticmethod
    def _release_tuition_claim(student_id, transaction_id, headers):
        try:
            response = requests.delete(
                f"{TUITION_SERVICE_URL}/api/v1/tuition/"
                f"{quote(student_id, safe='')}/claim/{quote(transaction_id, safe='')}",
                headers=headers,
                timeout=5,
            )
            if response.status_code != status.HTTP_200_OK:
                logger.error(
                    "Could not release tuition claim for transaction %s (HTTP %s)",
                    transaction_id,
                    response.status_code,
                )
        except requests.RequestException:
            logger.exception("Could not release tuition claim for transaction %s", transaction_id)

    @staticmethod
    def _mark_transaction_failed(db_session, transaction_id):
        try:
            if not TransactionModel.update_status(db_session, transaction_id, "FAILED"):
                logger.error(
                    "Could not mark transaction %s FAILED after a possible debit",
                    transaction_id,
                )
        except Exception:
            logger.exception(
                "Could not record failure for transaction %s after a possible debit",
                transaction_id,
            )
