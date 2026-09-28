import smtplib
from email.message import EmailMessage

from backend.payment_service.config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)


def send_otp_email(recipient, transaction_id, otp_code, expires_at):
    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL must be configured")

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
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)
