from datetime import datetime, timezone

from flask_login import UserMixin

from db import db


class Organization(db.Model):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    users = db.relationship('User', backref='organization', lazy=True)
    books = db.relationship('Book', backref='organization', lazy=True)
    members = db.relationship('Member', backref='organization', lazy=True)
    transactions = db.relationship('Transaction', backref='organization', lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(200))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')  # 'admin' or 'staff'
    api_key = db.Column(db.String(64), unique=True)
    reset_token = db.Column(db.String(128), unique=True)
    reset_token_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def is_admin(self):
        return self.role == 'admin'

    @property
    def display_name(self):
        return self.name or self.email.split('@')[0]


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    authors = db.Column(db.String(300))
    isbn = db.Column(db.String(50))
    publisher = db.Column(db.String(200))
    pages = db.Column(db.Integer)
    stock = db.Column(db.Integer, nullable=False, default=0)
    rent_fee = db.Column(db.Float, nullable=False, default=10.0)

    __table_args__ = (
        db.Index('idx_books_org_isbn', 'org_id', 'isbn'),
        db.Index('idx_books_org_title', 'org_id', 'title'),
    )


class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    debt = db.Column(db.Float, nullable=False, default=0)


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    issue_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime)
    fee_charged = db.Column(db.Float, nullable=False, default=0)

    book = db.relationship('Book')
    member = db.relationship('Member')

    __table_args__ = (
        db.Index('idx_transactions_org_book_id', 'org_id', 'book_id'),
        db.Index('idx_transactions_org_member_id', 'org_id', 'member_id'),
        db.Index('idx_transactions_org_return_date', 'org_id', 'return_date'),
    )


class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')  # active, cancelled, fulfilled
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    book = db.relationship('Book')
    member = db.relationship('Member')

    __table_args__ = (
        db.Index('idx_reservations_org_book_status', 'org_id', 'book_id', 'status'),
        db.Index('idx_reservations_org_member_status', 'org_id', 'member_id', 'status'),
    )


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User')

    __table_args__ = (
        db.Index('idx_audit_logs_org_created', 'org_id', 'created_at'),
    )
