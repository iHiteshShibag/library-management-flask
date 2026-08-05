from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

import config

db = SQLAlchemy()
migrate = Migrate()


def init_app(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Production connection-pool settings.
    # pool_pre_ping validates connections before checkout so stale connections
    # (e.g. after a DB restart or idle-timeout) don't surface as 500 errors.
    # pool_recycle closes connections that have been open longer than 30 min,
    # preventing Postgres from dropping them server-side first.
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,          # persistent connections kept open
        'max_overflow': 10,      # extra connections allowed under load
        'pool_timeout': 30,      # seconds to wait for a free connection
        'pool_recycle': 1800,    # recycle connections every 30 minutes
        'pool_pre_ping': True,   # health-check before each checkout
    }
    db.init_app(app)
    migrate.init_app(app, db)
