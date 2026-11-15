import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("omniva.email")


def send_password_reset(email: str, token: str) -> None:
    if not (settings.smtp_host and settings.email_from):
        return
    message = EmailMessage()
    message["Subject"] = "Reset your OMNIVA AI password"
    message["From"] = settings.email_from
    message["To"] = email
    message.set_content(
        "A password reset was requested for your account. "
        "Use this one-time token in the OMNIVA password reset form. "
        "It expires shortly. If you did not request this, ignore this message.\n\n"
        f"Reset token: {token}"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except OSError, smtplib.SMTPException:
        # Avoid logging the address, reset token, SMTP response, or provider details.
        logger.error("Password reset email delivery failed")
