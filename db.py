from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

import config

db = SQLAlchemy()
migrate = Migrate()


def init_app(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Use NullPool to avoid 'cannot notify on un-acquired lock' errors
    # caused by Eventlet monkey-patching SQLAlchemy's default QueuePool.
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'poolclass': NullPool,
    }
    db.init_app(app)
    migrate.init_app(app, db)
