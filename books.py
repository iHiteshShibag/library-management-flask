import csv
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
import requests

from db import db
from models import Book
from auth import require_role
from audit import log_action

bp = Blueprint('books', __name__)

MAX_IMPORT_COUNT = 200
PER_PAGE = 25


@bp.route('/books')
@login_required
def books():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Book.query.filter_by(org_id=current_user.org_id)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(Book.title.ilike(like), Book.authors.ilike(like)))
    pagination = query.order_by(Book.title).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('books.html', pagination=pagination, books=pagination.items, q=q)


@bp.route('/books/export.csv')
@login_required
def export_books_csv():
    rows = Book.query.filter_by(org_id=current_user.org_id).order_by(Book.title).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['id', 'title', 'authors', 'isbn', 'publisher', 'pages', 'stock', 'rent_fee'])
        yield buf.getvalue()
        for b in rows:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow([b.id, b.title, b.authors, b.isbn, b.publisher, b.pages, b.stock, b.rent_fee])
            yield buf.getvalue()

    return Response(generate(), mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename=books.csv'})


@bp.route('/books/add', methods=['POST'])
@login_required
def add_book():
    title = request.form['title'].strip()
    authors = request.form.get('authors', '').strip()
    isbn = request.form.get('isbn', '').strip()
    publisher = request.form.get('publisher', '').strip()
    pages = int(request.form.get('pages') or 0)
    stock = int(request.form.get('stock') or 0)
    rent_fee = float(request.form.get('rent_fee') or 10.0)
    db.session.add(Book(org_id=current_user.org_id, title=title, authors=authors, isbn=isbn,
                         publisher=publisher, pages=pages, stock=stock, rent_fee=rent_fee))
    log_action('book.create', f'Added "{title}"')
    db.session.commit()
    flash('Book added.')
    return redirect(url_for('books.books'))


@bp.route('/books/<int:book_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
def delete_book(book_id):
    book = Book.query.filter_by(id=book_id, org_id=current_user.org_id).first_or_404()
    try:
        db.session.delete(book)
        log_action('book.delete', f'Deleted "{book.title}"')
        db.session.commit()
        flash('Book deleted.')
    except IntegrityError:
        db.session.rollback()
        flash('Cannot delete this book — it has existing issue/return history.')
    return redirect(url_for('books.books'))


@bp.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    book = Book.query.filter_by(id=book_id, org_id=current_user.org_id).first_or_404()
    if request.method == 'POST':
        book.title = request.form['title'].strip()
        book.authors = request.form.get('authors', '').strip()
        book.isbn = request.form.get('isbn', '').strip()
        book.publisher = request.form.get('publisher', '').strip()
        book.pages = int(request.form.get('pages') or 0)
        book.stock = int(request.form.get('stock') or 0)
        book.rent_fee = float(request.form.get('rent_fee') or 10.0)
        log_action('book.edit', f'Edited "{book.title}"')
        db.session.commit()
        flash('Book updated.')
        return redirect(url_for('books.books'))
    return render_template('edit_book.html', book=book)


# Import from Frappe API
@bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_books():
    if request.method == 'POST':
        title = request.form.get('title', '')
        page = max(1, int(request.form.get('page') or 1))
        count = int(request.form.get('count') or 20)
        count = max(1, min(count, MAX_IMPORT_COUNT))
        # API gives 20 books per page; we'll loop pages if count >20
        url = 'https://frappe.io/api/method/frappe-library'
        existing_isbns = {isbn for isbn, in db.session.query(Book.isbn)
                           .filter(Book.org_id == current_user.org_id, Book.isbn.isnot(None), Book.isbn != '')}
        imported = 0
        skipped = 0
        remaining = count
        p = page
        while remaining > 0:
            params = {'title': title, 'page': p}
            try:
                r = requests.get(url, params=params, timeout=10)
                data = r.json().get('message', [])
            except Exception as e:
                flash('Failed to fetch from API: ' + str(e))
                break
            if not data:
                break
            for item in data:
                # frappe-library's response has inconsistent key whitespace
                # (e.g. "  num_pages" with leading spaces), so normalize first.
                item = {k.strip(): v for k, v in item.items()}
                isbn = item.get('isbn')
                if isbn and isbn in existing_isbns:
                    skipped += 1
                    continue
                db.session.add(Book(
                    org_id=current_user.org_id,
                    title=item.get('title'),
                    authors=item.get('authors'),
                    isbn=isbn,
                    publisher=item.get('publisher'),
                    pages=int(item.get('num_pages') or 0),
                    stock=1,
                ))
                if isbn:
                    existing_isbns.add(isbn)
                imported += 1
                remaining -= 1
                if remaining <= 0:
                    break
            p += 1
        log_action('book.import', f'Imported {imported} book(s), skipped {skipped} duplicate ISBN(s)')
        db.session.commit()
        msg = f'Imported {imported} books.'
        if skipped:
            msg += f' Skipped {skipped} already in your catalog (duplicate ISBN).'
        flash(msg)
        return redirect(url_for('books.books'))
    return render_template('import.html')
