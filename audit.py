from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from db import db
from models import AuditLog
from auth import require_role

bp = Blueprint('audit', __name__, url_prefix='/settings')

PER_PAGE = 50


def log_action(action, description=''):
    """Record an audit entry. Does not commit — caller commits as part of its own transaction."""
    db.session.add(AuditLog(
        org_id=current_user.org_id,
        user_id=current_user.id,
        action=action,
        description=description,
    ))


@bp.route('/audit-log')
@login_required
@require_role('admin')
def audit_log():
    page = request.args.get('page', 1, type=int)
    pagination = (AuditLog.query
                  .filter_by(org_id=current_user.org_id)
                  .order_by(AuditLog.id.desc())
                  .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template('audit_log.html', pagination=pagination)


def init_app(app):
    app.register_blueprint(bp)
