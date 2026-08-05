import os

import pytest

# The app's dashboard queries use Postgres-only SQL (date_trunc), so tests
# run against a real (separate) Postgres database rather than SQLite —
# SQLite would silently pass on everything except the one dialect-specific
# query, which is exactly the kind of gap a smoke suite exists to catch.
# Override via TEST_DATABASE_URL if your Postgres isn't on the default
# docker-compose port/credentials from README.
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ['DATABASE_URL'] = os.environ.get(
    'TEST_DATABASE_URL', 'postgresql://library:library_dev_pw@localhost:5432/library_test'
)

import app as app_module  # noqa: E402  (must import after env vars are set)
from db import db  # noqa: E402


@pytest.fixture(scope='session')
def app():
    flask_app = app_module.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    app_module.limiter.enabled = False

    # Short-lived contexts only: holding one app context open across the
    # whole yield (spanning every test-client request) fights with the test
    # client pushing its own per-request context, and previously left a
    # transaction dangling on the pooled connection — which then deadlocked
    # this very drop_all against the tables it needed to drop.
    with flask_app.app_context():
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def signup(client, email, password='testpass123', org_name=None):
    data = {'email': email, 'password': password}
    if org_name is not None:
        data['org_name'] = org_name
    return client.post('/signup', data=data, follow_redirects=True)


def login(client, email, password='testpass123'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)
