from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_login import current_user
from sqlalchemy import update

from db import db
from models import Book, Member, Transaction
from extensions import csrf

bp = Blueprint('api', __name__, url_prefix='/api/v1')


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(error='Unauthorized. Pass "Authorization: Bearer <api_key>".'), 401
        return view(*args, **kwargs)
    return wrapped


def book_dict(b):
    return {
        'id': b.id, 'title': b.title, 'authors': b.authors, 'isbn': b.isbn,
        'publisher': b.publisher, 'pages': b.pages, 'stock': b.stock, 'rent_fee': b.rent_fee,
    }


def member_dict(m):
    return {'id': m.id, 'name': m.name, 'phone': m.phone, 'email': m.email, 'debt': m.debt}


def transaction_dict(t):
    return {
        'id': t.id, 'book_id': t.book_id, 'member_id': t.member_id,
        'book_title': t.book.title if t.book else None,
        'member_name': t.member.name if t.member else None,
        'issue_date': t.issue_date.isoformat(),
        'return_date': t.return_date.isoformat() if t.return_date else None,
        'fee_charged': t.fee_charged,
    }


@bp.route('/books', methods=['GET', 'POST'])
@api_login_required
def api_books():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if not data.get('title'):
            return jsonify(error='"title" is required.'), 400
        book = Book(
            org_id=current_user.org_id,
            title=data['title'],
            authors=data.get('authors'),
            isbn=data.get('isbn'),
            publisher=data.get('publisher'),
            pages=data.get('pages') or 0,
            stock=data.get('stock') or 0,
            rent_fee=data.get('rent_fee') or 10.0,
        )
        db.session.add(book)
        db.session.commit()
        return jsonify(book_dict(book)), 201

    q = request.args.get('q', '').strip()
    query = Book.query.filter_by(org_id=current_user.org_id)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(Book.title.ilike(like), Book.authors.ilike(like)))
    books = query.order_by(Book.title).all()
    return jsonify([book_dict(b) for b in books])


@bp.route('/books/<int:book_id>', methods=['GET', 'PATCH', 'DELETE'])
@api_login_required
def api_book_detail(book_id):
    book = Book.query.filter_by(id=book_id, org_id=current_user.org_id).first()
    if not book:
        return jsonify(error='Not found.'), 404

    if request.method == 'DELETE':
        if current_user.role != 'admin':
            return jsonify(error='Forbidden.'), 403
        db.session.delete(book)
        db.session.commit()
        return '', 204

    if request.method == 'PATCH':
        data = request.get_json(silent=True) or {}
        for field in ('title', 'authors', 'isbn', 'publisher', 'pages', 'stock', 'rent_fee'):
            if field in data:
                setattr(book, field, data[field])
        db.session.commit()

    return jsonify(book_dict(book))


@bp.route('/members', methods=['GET', 'POST'])
@api_login_required
def api_members():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if not data.get('name'):
            return jsonify(error='"name" is required.'), 400
        member = Member(org_id=current_user.org_id, name=data['name'],
                         phone=data.get('phone'), email=data.get('email'))
        db.session.add(member)
        db.session.commit()
        return jsonify(member_dict(member)), 201

    members = Member.query.filter_by(org_id=current_user.org_id).order_by(Member.name).all()
    return jsonify([member_dict(m) for m in members])


@bp.route('/transactions', methods=['GET'])
@api_login_required
def api_transactions():
    rows = (Transaction.query.filter_by(org_id=current_user.org_id)
            .order_by(Transaction.id.desc()).limit(200).all())
    return jsonify([transaction_dict(t) for t in rows])


@bp.route('/issue', methods=['POST'])
@api_login_required
def api_issue():
    data = request.get_json(silent=True) or {}
    book_id = data.get('book_id')
    member_id = data.get('member_id')
    org_id = current_user.org_id
    if not book_id or not member_id:
        return jsonify(error='"book_id" and "member_id" are required.'), 400

    member = Member.query.filter_by(id=member_id, org_id=org_id).first()
    if not member:
        return jsonify(error='Member not found.'), 404
    if member.debt > 500:
        return jsonify(error='Member debt exceeds 500 — cannot issue.'), 409

    result = db.session.execute(
        update(Book).where(Book.id == book_id, Book.org_id == org_id, Book.stock > 0)
        .values(stock=Book.stock - 1)
    )
    if result.rowcount == 0:
        db.session.rollback()
        return jsonify(error='Book not available.'), 409

    tr = Transaction(org_id=org_id, book_id=book_id, member_id=member_id,
                      issue_date=datetime.now(timezone.utc))
    db.session.add(tr)
    db.session.commit()
    return jsonify(transaction_dict(tr)), 201


@bp.route('/return', methods=['POST'])
@api_login_required
def api_return():
    data = request.get_json(silent=True) or {}
    trans_id = data.get('transaction_id')
    org_id = current_user.org_id
    if not trans_id:
        return jsonify(error='"transaction_id" is required.'), 400

    tr = Transaction.query.filter_by(id=trans_id, org_id=org_id).first()
    if not tr or tr.return_date is not None:
        return jsonify(error='Invalid transaction.'), 404

    issue_dt = tr.issue_date if tr.issue_date.tzinfo else tr.issue_date.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    late_days = max(0, (now - issue_dt).days - 7)
    book = Book.query.filter_by(id=tr.book_id, org_id=org_id).first()
    fee = late_days * (book.rent_fee if book else 10.0)

    result = db.session.execute(
        update(Transaction)
        .where(Transaction.id == trans_id, Transaction.org_id == org_id, Transaction.return_date.is_(None))
        .values(return_date=now, fee_charged=fee)
    )
    if result.rowcount == 0:
        db.session.rollback()
        return jsonify(error='Invalid transaction.'), 404

    db.session.execute(update(Book).where(Book.id == tr.book_id, Book.org_id == org_id)
                        .values(stock=Book.stock + 1))
    db.session.execute(update(Member).where(Member.id == tr.member_id, Member.org_id == org_id)
                        .values(debt=Member.debt + fee))
    db.session.commit()
    return jsonify(transaction_dict(tr))


@bp.route('/me', methods=['GET'])
@api_login_required
def api_me():
    return jsonify(id=current_user.id, email=current_user.email, name=current_user.display_name,
                    role=current_user.role, org_id=current_user.org_id)


@bp.errorhandler(404)
def api_not_found(e):
    return jsonify(error='Not found.'), 404


def init_app(app):
    csrf.exempt(bp)
    app.register_blueprint(bp)
