from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

import config

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, storage_uri=config.RATELIMIT_STORAGE_URI)

# message_queue lets multiple Gunicorn/eventlet workers share broadcast events
# (each worker otherwise only knows about its own locally-connected clients).
# Unset in dev (single process) -> falls back to in-process broadcast, no Redis needed.
# cors_allowed_origins=None means "same origin only" — the safest default.
# Set SOCKETIO_CORS_ALLOWED_ORIGINS in .env for production if needed.
socketio = SocketIO(
    message_queue=config.SOCKETIO_MESSAGE_QUEUE,
    cors_allowed_origins=config.SOCKETIO_CORS_ALLOWED_ORIGINS,
    async_mode='eventlet',
)
