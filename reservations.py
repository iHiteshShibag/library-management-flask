from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from db import db
from models import Book, Member, Reservation
from audit import log_action

bp = Blueprint('reservations', __name__, url_prefix='/reservations')


@bp.route('')
@login_required
def reservations():
    rows = (Reservation.query
            .filter_by(org_id=current_user.org_id, status='active')
            .join(Book).join(Member)
            .order_by(Reservation.book_id, Reservation.created_at)
            .all())
    books = Book.query.filter_by(org_id=current_user.org_id).order_by(Book.title).all()
    members = Member.query.filter_by(org_id=current_user.org_id).order_by(Member.name).all()
    return render_template('reservations.html', reservations=rows, books=books, members=members)


@bp.route('/add', methods=['POST'])
@login_required
def add_reservation():
    book_id = request.form.get('book_id', type=int)
    member_id = request.form.get('member_id', type=int)
    org_id = current_user.org_id

    if not book_id or not member_id:
        flash('Select a book and a member first.')
        return redirect(url_for('reservations.reservations'))

    book = Book.query.filter_by(id=book_id, org_id=org_id).first()
    member = Member.query.filter_by(id=member_id, org_id=org_id).first()
    if not book or not member:
        flash('Book or member not found.')
        return redirect(url_for('reservations.reservations'))

    existing = Reservation.query.filter_by(org_id=org_id, book_id=book_id, member_id=member_id,
                                            status='active').first()
    if existing:
        flash(f'{member.name} already has an active reservation on "{book.title}".')
        return redirect(url_for('reservations.reservations'))

    db.session.add(Reservation(org_id=org_id, book_id=book_id, member_id=member_id))
    log_action('reservation.create', f'Reserved "{book.title}" for {member.name}')
    db.session.commit()
    flash('Reservation placed.')
    return redirect(url_for('reservations.reservations'))


@bp.route('/<int:reservation_id>/cancel', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    reservation = Reservation.query.filter_by(id=reservation_id, org_id=current_user.org_id,
                                                status='active').first_or_404()
    reservation.status = 'cancelled'
    log_action('reservation.cancel', f'Cancelled reservation #{reservation_id}')
    db.session.commit()
    flash('Reservation cancelled.')
    return redirect(url_for('reservations.reservations'))


def init_app(app):
    app.register_blueprint(bp)
