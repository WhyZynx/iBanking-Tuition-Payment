import logging
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from backend.payment_service.config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_USERNAME,
)

logger = logging.getLogger(__name__)


def _deliver(message):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        if SMTP_STARTTLS:
            server.starttls()
            logger.info("SMTP STARTTLS succeeded for host=%s port=%s", SMTP_HOST, SMTP_PORT)
        if SMTP_USERNAME or SMTP_PASSWORD:
            if not (SMTP_USERNAME and SMTP_PASSWORD):
                raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must both be configured")
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            logger.info("SMTP authentication succeeded for configured sender")
        server.send_message(message)


def send_otp_email(recipient, transaction_id, otp_code, expires_at):
    if not (SMTP_HOST and SMTP_FROM_EMAIL):
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL must be configured")

    local_part, separator, domain = recipient.partition("@")
    safe_recipient = f"{local_part[:1]}***@{domain}" if separator else "***"
    logger.info(
        "OTP email send started: recipient=%s host=%s port=%s transaction_id=%s",
        safe_recipient,
        SMTP_HOST,
        SMTP_PORT,
        transaction_id,
    )

    message = EmailMessage()
    message["Subject"] = "iBanking - OTP Verification"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = recipient
    message.set_content(
        f"Your OTP is {otp_code}. It expires in 5 minutes "
        f"(at {expires_at:%Y-%m-%d %H:%M:%S}).\n"
        f"Transaction ID: {transaction_id}\n"
    )

    _deliver(message)
    logger.info(
        "OTP email send succeeded: recipient=%s transaction_id=%s",
        safe_recipient,
        transaction_id,
    )
def send_payment_success_email(
    email,
    transaction_id,
    student_id,
    student_name,
    amount,
    account_number,
    completed_at,
):
    message = MIMEMultipart()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = email
    message["Subject"] = "iBanking - Payment Successful"

    body = f"""
Your tuition payment has been completed successfully.

Transaction ID: {transaction_id}
Student ID: {student_id}
Student Name: {student_name}
Amount: {amount} VND
Payment Account: {account_number}
Completed At: {completed_at}

Thank you for using iBanking.
"""

    message.attach(MIMEText(body, "plain", "utf-8"))

    _deliver(message)
