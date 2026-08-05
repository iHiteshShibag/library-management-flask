import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError(
        'SECRET_KEY is not set. Copy .env.example to .env and set a real value '
        '(e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).'
    )

DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError(
        'DATABASE_URL is not set. Copy .env.example to .env and point it at your '
        'Postgres instance (e.g. postgresql://library:library_dev_pw@localhost:5432/library).'
    )
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Optional: password-reset emails and due-date reminders. If unset, these are
# logged/flashed instead of sent (see mailer.py) so the app still works in dev.
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_SMTP_HOST = os.environ.get('EMAIL_SMTP_HOST', 'smtp.gmail.com')
EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '587'))

# Session cookie security. SESSION_COOKIE_SECURE defaults to false so login
# keeps working over plain http:// in local dev — set it true in any
# deployment served over HTTPS (it makes the browser refuse to send the
# cookie over a plain http:// connection, so turning it on before HTTPS is
# in front of the app would silently break login).
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

# Rate-limit counters storage. In-memory is correct only for a single
# process — switch to a shared store (e.g. redis://localhost:6379) once
# running more than one worker/instance, or limits become per-worker instead
# of global.
RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

# Optional: error tracking. Unset by default — Sentry is only initialized if
# a DSN is provided (see app.py).
SENTRY_DSN = os.environ.get('SENTRY_DSN')

# Message queue backing Socket.IO broadcasts across worker processes. None is
# correct for a single dev process; set to a redis:// URL once running more
# than one Gunicorn worker, same reasoning as RATELIMIT_STORAGE_URI above.
SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE')

# Allowed origins for Socket.IO WebSocket connections. None defaults to the
# Flask server's own origin (same-origin only — the safest default). In
# production, set this to your exact domain, e.g.:
# SOCKETIO_CORS_ALLOWED_ORIGINS=https://library.example.com
# or a comma-separated list for multiple domains.
_cors_raw = os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS')
if _cors_raw:
    _cors_split = [o.strip() for o in _cors_raw.split(',') if o.strip()]
    SOCKETIO_CORS_ALLOWED_ORIGINS = _cors_split[0] if len(_cors_split) == 1 else _cors_split
else:
    SOCKETIO_CORS_ALLOWED_ORIGINS = None  # same-origin only
