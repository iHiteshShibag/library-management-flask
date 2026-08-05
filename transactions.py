import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from sqlalchemy import update

from db import db
from models import Book, Member, Transaction, Reservation
from audit import log_action
from extensions import socketio
from dashboard import compute_stats

bp = Blueprint('transactions', __name__)

PER_PAGE = 25


@bp.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    if request.method == 'POST':
        book_id = request.form.get('book_id', type=int)
        member_id = request.form.get('member_id', type=int)
        org_id = current_user.org_id

        if not book_id or not member_id:
            flash('Select a book and a member first.')
            return redirect(url_for('transactions.issue'))

        member = Member.query.filter_by(id=member_id, org_id=org_id).first()
        if not member:
            flash('Member not found.')
            return redirect(url_for('transactions.issue'))
        if member.debt > 500:
            flash('Member debt exceeds ₹500 — cannot issue.')
            return redirect(url_for('transactions.issue'))

        # atomically claim a copy: this UPDATE only succeeds if stock is
        # still > 0 at commit time, closing the check-then-act race where
        # two concurrent requests could both pass a plain SELECT check.
        result = db.session.execute(
            update(Book)
            .where(Book.id == book_id, Book.org_id == org_id, Book.stock > 0)
            .values(stock=Book.stock - 1)
        )
        if result.rowcount == 0:
            db.session.rollback()
            flash('Book not available.')
            return redirect(url_for('transactions.issue'))

        issue_date = datetime.now(timezone.utc)
        db.session.add(Transaction(org_id=org_id, book_id=book_id, member_id=member_id,
                                    issue_date=issue_date))
        # auto-fulfill a matching hold, if this member had one on this book
        db.session.execute(
            update(Reservation)
            .where(Reservation.org_id == org_id, Reservation.book_id == book_id,
                   Reservation.member_id == member_id, Reservation.status == 'active')
            .values(status='fulfilled')
        )
        log_action('transaction.issue', f'Issued book #{book_id} to member #{member_id}')
        db.session.commit()

        book = db.session.get(Book, book_id)
        socketio.emit('dashboard_update', {
            'stats': compute_stats(org_id),
            'activity': f'{member.name} borrowed "{book.title}"' if book else 'A book was issued.',
        }, room=f'org-{org_id}')

        flash('Book issued.')
        return redirect(url_for('transactions.transactions'))
    # GET
    books = Book.query.filter_by(org_id=current_user.org_id).filter(Book.stock > 0).order_by(Book.title).all()
    members = Member.query.filter_by(org_id=current_user.org_id).order_by(Member.name).all()
    return render_template('issue.html', books=books, members=members)


@bp.route('/return', methods=['GET', 'POST'])
@login_required
def return_book():
    if request.method == 'POST':
        trans_id = request.form.get('transaction_id', type=int)
        org_id = current_user.org_id

        if not trans_id:
            flash('Select an outstanding issue first.')
            return redirect(url_for('transactions.return_book'))

        tr = Transaction.query.filter_by(id=trans_id, org_id=org_id).first()
        if not tr or tr.return_date is not None:
            flash('Invalid transaction.')
            return redirect(url_for('transactions.transactions'))

        # compute fee: simple rule -> days late * rent_fee (assume 7-day free period)
        issue_dt = tr.issue_date
        if issue_dt.tzinfo is None:
            issue_dt = issue_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days = (now - issue_dt).days
        grace = 7
        late_days = max(0, days - grace)
        book = Book.query.filter_by(id=tr.book_id, org_id=org_id).first()
        rent_fee = book.rent_fee if book else 10.0
        fee = late_days * rent_fee

        # atomically claim this return: only succeeds if still un-returned
        # at commit time, closing the race where two concurrent requests
        # for the same transaction could both pass the plain check above
        # and double-credit stock/debt.
        result = db.session.execute(
            update(Transaction)
            .where(Transaction.id == trans_id, Transaction.org_id == org_id,
                   Transaction.return_date.is_(None))
            .values(return_date=now, fee_charged=fee)
        )
        if result.rowcount == 0:
            db.session.rollback()
            flash('Invalid transaction.')
            return redirect(url_for('transactions.transactions'))

        db.session.execute(
            update(Book).where(Book.id == tr.book_id, Book.org_id == org_id)
            .values(stock=Book.stock + 1)
        )
        db.session.execute(
            update(Member).where(Member.id == tr.member_id, Member.org_id == org_id)
            .values(debt=Member.debt + fee)
        )
        log_action('transaction.return', f'Returned transaction #{trans_id}, fee ₹{fee:.2f}')
        db.session.commit()

        member = db.session.get(Member, tr.member_id)
        socketio.emit('dashboard_update', {
            'stats': compute_stats(org_id),
            'activity': f'{member.name} returned "{book.title}"' if member and book else 'A book was returned.',
        }, room=f'org-{org_id}')

        debt = member.debt
        if debt > 500:
            flash(f'Book returned. Member debt is ₹{debt:.2f} — exceeds ₹500.')
        else:
            flash(f'Book returned. Fee charged: ₹{fee:.2f}')
        return redirect(url_for('transactions.transactions'))
    # GET: show outstanding transactions (not returned)
    rows = (Transaction.query
            .filter_by(org_id=current_user.org_id, return_date=None)
            .join(Book).join(Member)
            .all())
    return render_template('return.html', trans=rows)


@bp.route('/transactions')
@login_required
def transactions():
    page = request.args.get('page', 1, type=int)
    pagination = (Transaction.query
                  .filter_by(org_id=current_user.org_id)
                  .order_by(Transaction.id.desc())
                  .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template('transactions.html', pagination=pagination, trans=pagination.items)


@bp.route('/transactions/export.csv')
@login_required
def export_transactions_csv():
    rows = (Transaction.query
            .filter_by(org_id=current_user.org_id)
            .order_by(Transaction.id.desc())
            .all())

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['id', 'book', 'member', 'issue_date', 'return_date', 'fee_charged'])
        yield buf.getvalue()
        for t in rows:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow([
                t.id,
                t.book.title if t.book else '',
                t.member.name if t.member else '',
                t.issue_date.strftime('%Y-%m-%d %H:%M'),
                t.return_date.strftime('%Y-%m-%d %H:%M') if t.return_date else '',
                f'{t.fee_charged:.2f}',
            ])
            yield buf.getvalue()

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=transactions.csv'},
    )
