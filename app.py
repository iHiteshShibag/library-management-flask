from flask import Flask, render_template
from flask_login import current_user
from flask_socketio import join_room, disconnect

import config
import db as db_module
import auth
import books
import members
import transactions
import dashboard
import settings
import audit
import reservations
import api
import reminders
from db import db
from extensions import csrf, limiter, socketio

if config.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    sentry_sdk.init(dsn=config.SENTRY_DSN, integrations=[FlaskIntegration()])

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

csrf.init_app(app)
limiter.init_app(app)
socketio.init_app(app)
db_module.init_app(app)
auth.init_app(app)
dashboard.init_app(app)
settings.init_app(app)
audit.init_app(app)
reservations.init_app(app)
api.init_app(app)
reminders.init_app(app)
app.register_blueprint(books.bp)
app.register_blueprint(members.bp)
app.register_blueprint(transactions.bp)


@app.route('/healthz')
def healthz():
    db.session.execute(db.text('SELECT 1'))
    return {'status': 'ok'}


@app.after_request
def set_security_headers(response):
    # Prevent the page from being loaded in an iframe (clickjacking defence).
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Stop browsers from MIME-sniffing a response away from the declared content-type.
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Send only the origin (no path/query) in the Referer header for cross-origin requests.
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Disable access to sensitive browser features not used by this app.
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # Basic Content-Security-Policy — tighten further once inline styles/scripts are audited.
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdn.socket.io; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    return response


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


@socketio.on('connect')
def handle_connect():
    # Reject anonymous sockets and put each client in a room keyed by their
    # org_id, so a 'dashboard_update' emit only reaches that org's clients —
    # the app is multi-tenant everywhere else, this can't be the exception.
    if not current_user.is_authenticated:
        disconnect()
        return
    join_room(f'org-{current_user.org_id}')


if __name__ == '__main__':
    # socketio.run wraps Werkzeug with eventlet's WSGI server so WebSocket
    # upgrade requests work in dev too — plain `app.run()` can't handle them.
    print(" * Server is running! Access it at: http://127.0.0.1:5000")
    socketio.run(app, debug=config.DEBUG)
