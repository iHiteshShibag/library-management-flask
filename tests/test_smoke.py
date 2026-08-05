# These tests share one database and run top-to-bottom in this file: signup
# is single-org (see auth.py), so "the first signup ever" is only true once
# per test run, and later tests deliberately build on state earlier ones left
# behind (an admin user, a book, a member) rather than re-creating it.
from conftest import login, signup

from db import db
from models import Book, Member, Organization, User


def test_first_signup_creates_org_and_becomes_admin(client, app):
    resp = signup(client, 'admin@smoketest.local', org_name='Smoke Test Library')
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email='admin@smoketest.local').first()
        assert user is not None
        assert user.role == 'admin'
        org = db.session.get(Organization, user.org_id)
        assert org.name == 'Smoke Test Library'


def test_second_signup_joins_existing_org_as_staff(client, app):
    resp = signup(client, 'staff@smoketest.local')
    assert resp.status_code == 200

    with app.app_context():
        admin = User.query.filter_by(email='admin@smoketest.local').first()
        staff = User.query.filter_by(email='staff@smoketest.local').first()
        assert staff is not None
        assert staff.role == 'staff'
        assert staff.org_id == admin.org_id


def test_login_rejects_wrong_password(client):
    resp = login(client, 'admin@smoketest.local', password='wrong-password')
    assert b'Invalid email or password' in resp.data


def test_login_accepts_correct_credentials(client):
    resp = login(client, 'admin@smoketest.local', password='testpass123')
    assert b'Logged in successfully' in resp.data


def test_admin_can_add_a_book(client, app):
    login(client, 'admin@smoketest.local')
    resp = client.post('/books/add', data={
        'title': 'Smoke Test Book', 'authors': 'Author A', 'isbn': '111',
        'stock': '2', 'rent_fee': '10',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Book.query.filter_by(title='Smoke Test Book').first() is not None


def test_staff_cannot_delete_a_book(client, app):
    with app.app_context():
        book = Book.query.filter_by(title='Smoke Test Book').first()
        book_id = book.id

    login(client, 'staff@smoketest.local')
    resp = client.post(f'/books/{book_id}/delete', follow_redirects=True)
    assert resp.status_code == 403


def test_issue_and_return_updates_stock_and_fee(client, app):
    from models import Transaction

    login(client, 'admin@smoketest.local')
    client.post('/members/add', data={'name': 'Smoke Member', 'phone': '555'}, follow_redirects=True)

    with app.app_context():
        book = Book.query.filter_by(title='Smoke Test Book').first()
        member = Member.query.filter_by(name='Smoke Member').first()
        book_id, member_id = book.id, member.id
        starting_stock = book.stock

    resp = client.post('/issue', data={'book_id': book_id, 'member_id': member_id}, follow_redirects=True)
    assert b'Book issued' in resp.data

    with app.app_context():
        assert db.session.get(Book, book_id).stock == starting_stock - 1
        trans_id = Transaction.query.filter_by(book_id=book_id, member_id=member_id).first().id

    resp = client.post('/return', data={'transaction_id': trans_id}, follow_redirects=True)
    assert b'Book returned' in resp.data

    with app.app_context():
        assert db.session.get(Book, book_id).stock == starting_stock


def test_api_key_authenticates_rest_api(client, app):
    login(client, 'admin@smoketest.local')
    client.post('/settings/profile/api-key/generate', follow_redirects=True)

    with app.app_context():
        admin = User.query.filter_by(email='admin@smoketest.local').first()
        api_key = admin.api_key
    assert api_key

    resp = client.get('/api/v1/me', headers={'Authorization': f'Bearer {api_key}'})
    assert resp.status_code == 200
    assert resp.get_json()['email'] == 'admin@smoketest.local'

    # A fresh client with no session cookie — otherwise Flask-Login would
    # authenticate this via the browser session regardless of the bogus key.
    anon_client = app.test_client()
    resp = anon_client.get('/api/v1/books', headers={'Authorization': 'Bearer not-a-real-key'})
    assert resp.status_code == 401


def test_healthz(client):
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'


def test_404_page(client):
    resp = client.get('/this-route-does-not-exist')
    assert resp.status_code == 404
    assert b'Page not found' in resp.data
