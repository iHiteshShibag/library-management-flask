import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

from db import db
from models import User
from auth import require_role, password_error
from audit import log_action

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        current_user.name = name or None
        db.session.commit()
        flash('Profile updated.')
        return redirect(url_for('settings.profile'))
    return render_template('settings_profile.html')


@bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect.')
        return redirect(url_for('settings.profile'))
    pw_error = password_error(new_password)
    if pw_error:
        flash(pw_error)
        return redirect(url_for('settings.profile'))
    current_user.password_hash = generate_password_hash(new_password)
    log_action('user.password_change', 'Changed own password')
    db.session.commit()
    flash('Password updated.')
    return redirect(url_for('settings.profile'))


@bp.route('/profile/api-key/generate', methods=['POST'])
@login_required
def generate_api_key():
    current_user.api_key = secrets.token_hex(32)
    log_action('user.api_key_generate', 'Generated a new API key')
    db.session.commit()
    flash(f'New API key generated — copy it now, it will not be shown again: {current_user.api_key}')
    return redirect(url_for('settings.profile'))


@bp.route('/profile/api-key/revoke', methods=['POST'])
@login_required
def revoke_api_key():
    current_user.api_key = None
    log_action('user.api_key_revoke', 'Revoked API key')
    db.session.commit()
    flash('API key revoked.')
    return redirect(url_for('settings.profile'))


@bp.route('/users')
@login_required
@require_role('admin')
def users():
    org_users = User.query.filter_by(org_id=current_user.org_id).order_by(User.email).all()
    return render_template('settings_users.html', users=org_users)


@bp.route('/users/add', methods=['POST'])
@login_required
@require_role('admin')
def add_user():
    email = request.form.get('email', '').strip().lower()
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'staff')
    if role not in ('admin', 'staff'):
        role = 'staff'
    if not email or not password:
        flash('Email and password are required.')
        return redirect(url_for('settings.users'))
    pw_error = password_error(password)
    if pw_error:
        flash(pw_error)
        return redirect(url_for('settings.users'))
    try:
        db.session.add(User(org_id=current_user.org_id, email=email, name=name or None,
                             password_hash=generate_password_hash(password), role=role))
        log_action('user.create', f'Added user "{email}" ({role})')
        db.session.commit()
        flash(f'User "{email}" added.')
    except IntegrityError:
        db.session.rollback()
        flash('A user with that email already exists.')
    return redirect(url_for('settings.users'))


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
def delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot remove your own account.')
        return redirect(url_for('settings.users'))
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    db.session.delete(user)
    log_action('user.delete', f'Removed user "{user.email}"')
    db.session.commit()
    flash('User removed.')
    return redirect(url_for('settings.users'))


def init_app(app):
    app.register_blueprint(bp)
