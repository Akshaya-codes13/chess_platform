import logging

logger = logging.getLogger(__name__)

# No email provider is configured yet. These functions are the single place
# to plug one in (SMTP or a transactional email API). Until then, messages
# are NOT sent; tokens are never logged.


def send_verification_email(email: str, token: str) -> None:
    logger.warning(
        "Email delivery is not configured; verification email to %s was not sent.",
        email,
    )


def send_password_reset_email(email: str, token: str) -> None:
    logger.warning(
        "Email delivery is not configured; password reset email to %s was not sent.",
        email,
    )


def send_email(email: str, subject: str, body: str) -> None:
    logger.warning(
        "Email delivery is not configured; notification email to %s was not sent.",
        email,
    )
