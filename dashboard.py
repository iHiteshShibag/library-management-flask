from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template
from flask_login import current_user
from sqlalchemy import func

from db import db
from models import Book, Member, Transaction

bp = Blueprint('dashboard', __name__)


def compute_stats(org_id):
    """Same counters shown on page load and pushed live over the
    'dashboard_update' socket event — kept in one place so the two never
    drift apart."""
    total_books = sum(b.stock for b in Book.query.filter_by(org_id=org_id).all()) or 0
    book_titles = Book.query.filter_by(org_id=org_id).count()
    total_members = Member.query.filter_by(org_id=org_id).count()

    active_loans = Transaction.query.filter_by(org_id=org_id, return_date=None).all()
    now = datetime.now(timezone.utc)
    overdue_count = 0
    for tr in active_loans:
        issue_dt = tr.issue_date if tr.issue_date.tzinfo else tr.issue_date.replace(tzinfo=timezone.utc)
        if (now - issue_dt).days > 7:
            overdue_count += 1

    outstanding_fines = sum(m.debt for m in Member.query.filter_by(org_id=org_id).all()) or 0

    return {
        'book_titles': book_titles,
        'total_copies': total_books,
        'total_members': total_members,
        'active_loans': len(active_loans),
        'overdue_count': overdue_count,
        'outstanding_fines': outstanding_fines,
    }


@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('landing.html')

    org_id = current_user.org_id
    stats = compute_stats(org_id)
    total_books = stats['total_copies']

    recent = (Transaction.query.filter_by(org_id=org_id)
              .order_by(Transaction.id.desc()).limit(5).all())

    # --- Stock overview: available copies (Book.stock) vs. copies currently out on loan ---
    issued_count = stats['active_loans']
    stock_overview = {
        'available': total_books,
        'issued': issued_count,
        'total': total_books + issued_count,
    }

    # --- Books by author: grouped by the raw free-text `authors` field, top 4 + "Others" ---
    author_rows = (db.session.query(Book.authors, func.count(Book.id))
                   .filter(Book.org_id == org_id, Book.authors.isnot(None), Book.authors != '')
                   .group_by(Book.authors)
                   .order_by(func.count(Book.id).desc())
                   .all())
    top_author_rows = author_rows[:4]
    others_count = sum(count for _, count in author_rows[4:])
    books_by_author = [{'label': name, 'count': count} for name, count in top_author_rows]
    if others_count:
        books_by_author.append({'label': 'Others', 'count': others_count})

    # --- Top borrowed books: by loan count, joined for title/authors ---
    top_books_rows = (db.session.query(Book, func.count(Transaction.id).label('loans'))
                       .join(Transaction, Transaction.book_id == Book.id)
                       .filter(Book.org_id == org_id)
                       .group_by(Book.id)
                       .order_by(func.count(Transaction.id).desc())
                       .limit(5)
                       .all())
    top_books = [{'title': b.title, 'authors': b.authors, 'loans': loans} for b, loans in top_books_rows]

    # --- Top authors: by loan count across their books ---
    top_authors_rows = (db.session.query(Book.authors, func.count(Transaction.id).label('loans'))
                         .join(Transaction, Transaction.book_id == Book.id)
                         .filter(Book.org_id == org_id, Book.authors.isnot(None), Book.authors != '')
                         .group_by(Book.authors)
                         .order_by(func.count(Transaction.id).desc())
                         .limit(5)
                         .all())
    top_authors = [{'name': name, 'loans': loans} for name, loans in top_authors_rows]

    # --- Trends over the last 8 weeks: borrow/return activity and fines collected ---
    # issue_date/return_date are stored as naive UTC wall-clock values (see transactions.py),
    # so cutoff and the reconstructed bucket keys below must also be naive to match them.
    now = datetime.utcnow()
    cutoff = now.replace(tzinfo=None) - timedelta(weeks=8)
    issued_weekly = dict((db.session.query(
        func.date_trunc('week', Transaction.issue_date), func.count(Transaction.id))
        .filter(Transaction.org_id == org_id, Transaction.issue_date >= cutoff)
        .group_by(func.date_trunc('week', Transaction.issue_date))
        .all()))
    returned_weekly = dict((db.session.query(
        func.date_trunc('week', Transaction.return_date), func.count(Transaction.id))
        .filter(Transaction.org_id == org_id, Transaction.return_date >= cutoff)
        .group_by(func.date_trunc('week', Transaction.return_date))
        .all()))
    fines_weekly = dict((db.session.query(
        func.date_trunc('week', Transaction.return_date), func.sum(Transaction.fee_charged))
        .filter(Transaction.org_id == org_id, Transaction.return_date >= cutoff, Transaction.fee_charged > 0)
        .group_by(func.date_trunc('week', Transaction.return_date))
        .all()))

    week_starts = sorted({d.date() for d in list(issued_weekly) + list(returned_weekly) + list(fines_weekly)})
    borrow_trend = {
        'labels': [d.strftime('%b %-d') for d in week_starts],
        'issued': [issued_weekly.get(datetime.combine(d, datetime.min.time()), 0) for d in week_starts],
        'returned': [returned_weekly.get(datetime.combine(d, datetime.min.time()), 0) for d in week_starts],
    }
    fines_trend = {
        'labels': [d.strftime('%b %-d') for d in week_starts],
        'amounts': [float(fines_weekly.get(datetime.combine(d, datetime.min.time()), 0) or 0) for d in week_starts],
    }

    return render_template(
        'index.html',
        stats=stats,
        recent=recent,
        stock_overview=stock_overview,
        books_by_author=books_by_author,
        top_books=top_books,
        top_authors=top_authors,
        borrow_trend=borrow_trend,
        fines_trend=fines_trend,
    )


def init_app(app):
    app.register_blueprint(bp)
