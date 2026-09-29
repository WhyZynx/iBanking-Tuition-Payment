import logging
import smtplib
from email.message import EmailMessage

from backend.payment_service.config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)

logger = logging.getLogger(__name__)


def send_otp_email(recipient, transaction_id, otp_code, expires_at):
    if not all((SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL)):
        raise RuntimeError(
            "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM_EMAIL must be configured"
        )

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

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.starttls()
        logger.info("SMTP STARTTLS succeeded for host=%s port=%s", SMTP_HOST, SMTP_PORT)
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        logger.info("SMTP authentication succeeded for configured sender")
        server.send_message(message)
        logger.info(
            "OTP email send succeeded: recipient=%s transaction_id=%s",
            safe_recipient,
            transaction_id,
        )
