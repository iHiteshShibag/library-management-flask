import logging
import smtplib
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


def send_email(to_address, subject, body):
    """Send an email if SMTP creds are configured. Returns True if actually sent,
    False if it only logged (dev fallback — no EMAIL_USER/EMAIL_PASSWORD set)."""
    if not config.EMAIL_USER or not config.EMAIL_PASSWORD:
        logger.info('Email not configured — would have sent to %s: %s\n%s', to_address, subject, body)
        return False

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = config.EMAIL_USER
    msg['To'] = to_address

    try:
        with smtplib.SMTP(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            server.sendmail(config.EMAIL_USER, [to_address], msg.as_string())
        return True
    except smtplib.SMTPException as e:
        logger.error('Failed to send email to %s via %s: %s', to_address, config.EMAIL_SMTP_HOST, e)
        return False
