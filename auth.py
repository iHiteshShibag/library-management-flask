import getpass
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import click
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

from db import db
from extensions import login_manager, limiter
from mailer import send_email
from models import Organization, User

bp = Blueprint('auth', __name__)

SLUG_RE = re.compile(r'[^a-z0-9]+')
MIN_PASSWORD_LENGTH = 8
RESET_TOKEN_TTL = timedelta(hours=1)


def password_error(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
    return None


def slugify(name):
    base = SLUG_RE.sub('-', name.strip().lower()).strip('-') or 'org'
    slug = base
    n = 2
    while Organization.query.filter_by(slug=slug).first() is not None:
        slug = f'{base}-{n}'
        n += 1
    return slug


def require_role(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.request_loader
def load_user_from_api_key(req):
    auth_header = req.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    api_key = auth_header[7:].strip()
    if not api_key:
        return None
    return User.query.filter_by(api_key=api_key).first()


@bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    # Single-org mode: the first signup founds the organization and becomes
    # its admin. Every signup after that just joins that same org as staff.
    org = Organization.query.first()
    if request.method == 'POST':
        org_name = request.form.get('org_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if (org is None and not org_name) or not email or not password:
            flash('Organization name, email, and password are all required.' if org is None
                  else 'Email and password are required.')
            return render_template('signup.html', org=org)
        pw_error = password_error(password)
        if pw_error:
            flash(pw_error)
            return render_template('signup.html', org=org)
        if User.query.filter_by(email=email).first() is not None:
            flash('An account with that email already exists.')
            return render_template('signup.html', org=org)

        if org is None:
            org = Organization(name=org_name, slug=slugify(org_name))
            db.session.add(org)
            db.session.flush()  # populate org.id before creating the user
            role = 'admin'
            welcome = f'Welcome to {org.name}! Your organization is ready.'
        else:
            role = 'staff'
            welcome = f'Welcome to {org.name}!'

        user = User(org_id=org.id, email=email,
                    password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(welcome)
        return redirect(url_for('dashboard.index'))
    return render_template('signup.html', org=org)


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('15 per minute', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('dashboard.index'))
        flash('Invalid email or password.')
    return render_template('login.html')


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Logged out.')
    return redirect(url_for('auth.login'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per hour', methods=['POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires = datetime.now(timezone.utc) + RESET_TOKEN_TTL
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=user.reset_token, _external=True)
            sent = send_email(user.email, 'Reset your LibraryOS password',
                               f'Click the link below to reset your password (expires in 1 hour):\n{reset_url}')
            if not sent:
                flash(f'Couldn\'t send that email automatically — here is your reset link: {reset_url}')
        # Same message whether or not the email exists, so this can't be used to enumerate accounts.
        flash('If that email is registered, a reset link has been sent.')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    expires = user.reset_token_expires if user else None
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not user or not expires or expires < datetime.now(timezone.utc):
        flash('That reset link is invalid or has expired.')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        pw_error = password_error(password)
        if pw_error:
            flash(pw_error)
            return render_template('reset_password.html', token=token)
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Password reset. Log in with your new password.')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token)


@click.command('create-admin')
def create_admin_command():
    """Create an admin login (prompts for details). Single-org mode: the
    first run founds the organization; every run after that just adds
    another admin to that same org, mirroring web signup."""
    org = Organization.query.first()
    founding = org is None
    if founding:
        org_name = input('Organization name: ').strip()
        if not org_name:
            print('Organization name is required.')
            return
    email = input('Admin email: ').strip().lower()
    password = getpass.getpass('Password: ')
    if not email or not password:
        print('Email and password are required.')
        return

    if founding:
        org = Organization(name=org_name, slug=slugify(org_name))
        db.session.add(org)
        db.session.flush()

    try:
        db.session.add(User(org_id=org.id, email=email,
                             password_hash=generate_password_hash(password), role='admin'))
        db.session.commit()
        print(f'Organization "{org.name}" created with admin "{email}".' if founding else
              f'Admin "{email}" added to "{org.name}".')
    except IntegrityError:
        db.session.rollback()
        print(f'A user with email "{email}" already exists.')


def init_app(app):
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access the library system.'
    app.register_blueprint(bp)
    app.cli.add_command(create_admin_command)
