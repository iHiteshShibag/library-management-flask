
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, requests, math
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'dev-secret-key'  # change for production

DB = 'library.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # create tables
    c.executescript(""" 
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        authors TEXT,
        isbn TEXT,
        publisher TEXT,
        pages INTEGER,
        stock INTEGER DEFAULT 0,
        rent_fee REAL DEFAULT 10.0
    );
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        debt REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER,
        member_id INTEGER,
        issue_date TEXT,
        return_date TEXT,
        fee_charged REAL DEFAULT 0,
        FOREIGN KEY(book_id) REFERENCES books(id),
        FOREIGN KEY(member_id) REFERENCES members(id)
    );
    """)
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# Books: list, add, edit, delete, search
@app.route('/books')
def books():
    q = request.args.get('q','').strip()
    conn = get_db()
    cur = conn.cursor()
    if q:
        cur.execute("SELECT * FROM books WHERE title LIKE ? OR authors LIKE ?", (f'%{q}%', f'%{q}%'))
    else:
        cur.execute("SELECT * FROM books")
    books = cur.fetchall()
    conn.close()
    return render_template('books.html', books=books, q=q)

@app.route('/books/add', methods=['POST'])
def add_book():
    title = request.form['title'].strip()
    authors = request.form.get('authors','').strip()
    isbn = request.form.get('isbn','').strip()
    publisher = request.form.get('publisher','').strip()
    pages = request.form.get('pages') or 0
    stock = int(request.form.get('stock') or 0)
    rent_fee = float(request.form.get('rent_fee') or 10.0)
    conn = get_db()
    conn.execute('INSERT INTO books (title, authors, isbn, publisher, pages, stock, rent_fee) VALUES (?,?,?,?,?,?,?)',
                 (title, authors, isbn, publisher, pages, stock, rent_fee))
    conn.commit()
    conn.close()
    flash('Book added.')
    return redirect(url_for('books'))

@app.route('/books/<int:book_id>/delete', methods=['POST'])
def delete_book(book_id):
    conn = get_db()
    conn.execute('DELETE FROM books WHERE id=?', (book_id,))
    conn.commit()
    conn.close()
    flash('Book deleted.')
    return redirect(url_for('books'))

@app.route('/books/<int:book_id>/edit', methods=['GET','POST'])
def edit_book(book_id):
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        title = request.form['title'].strip()
        authors = request.form.get('authors','').strip()
        isbn = request.form.get('isbn','').strip()
        publisher = request.form.get('publisher','').strip()
        pages = request.form.get('pages') or 0
        stock = int(request.form.get('stock') or 0)
        rent_fee = float(request.form.get('rent_fee') or 10.0)
        conn.execute('UPDATE books SET title=?, authors=?, isbn=?, publisher=?, pages=?, stock=?, rent_fee=? WHERE id=?',
                     (title, authors, isbn, publisher, pages, stock, rent_fee, book_id))
        conn.commit()
        conn.close()
        flash('Book updated.')
        return redirect(url_for('books'))
    cur.execute('SELECT * FROM books WHERE id=?', (book_id,))
    book = cur.fetchone()
    conn.close()
    return render_template('edit_book.html', book=book)

# Members
@app.route('/members')
def members():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM members')
    members = cur.fetchall()
    conn.close()
    return render_template('members.html', members=members)

@app.route('/members/add', methods=['POST'])
def add_member():
    name = request.form['name'].strip()
    phone = request.form.get('phone','').strip()
    conn = get_db()
    conn.execute('INSERT INTO members (name, phone) VALUES (?,?)', (name, phone))
    conn.commit()
    conn.close()
    flash('Member added.')
    return redirect(url_for('members'))

@app.route('/members/<int:member_id>/delete', methods=['POST'])
def delete_member(member_id):
    conn = get_db()
    conn.execute('DELETE FROM members WHERE id=?', (member_id,))
    conn.commit()
    conn.close()
    flash('Member deleted.')
    return redirect(url_for('members'))

# Issue book
@app.route('/issue', methods=['GET','POST'])
def issue():
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        book_id = int(request.form['book_id'])
        member_id = int(request.form['member_id'])
        # check stock
        cur.execute('SELECT stock FROM books WHERE id=?', (book_id,))
        book = cur.fetchone()
        if not book or book['stock'] <= 0:
            flash('Book not available.')
            conn.close()
            return redirect(url_for('issue'))
        # check member debt
        cur.execute('SELECT debt FROM members WHERE id=?', (member_id,))
        member = cur.fetchone()
        if not member:
            flash('Member not found.')
            conn.close()
            return redirect(url_for('issue'))
        if member['debt'] > 500:
            flash('Member debt exceeds ₹500 — cannot issue.')
            conn.close()
            return redirect(url_for('issue'))

        # proceed to issue
        issue_date = datetime.utcnow().isoformat()
        cur.execute('INSERT INTO transactions (book_id, member_id, issue_date) VALUES (?,?,?)',
                    (book_id, member_id, issue_date))
        cur.execute('UPDATE books SET stock = stock - 1 WHERE id=?', (book_id,))
        conn.commit()
        conn.close()
        flash('Book issued.')
        return redirect(url_for('transactions'))
    # GET
    cur.execute('SELECT * FROM books WHERE stock>0')
    books = cur.fetchall()
    cur.execute('SELECT * FROM members')
    members = cur.fetchall()
    conn.close()
    return render_template('issue.html', books=books, members=members)

# Return book
@app.route('/return', methods=['GET','POST'])
def return_book():
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        trans_id = int(request.form['transaction_id'])
        # fetch transaction
        cur.execute('SELECT * FROM transactions WHERE id=?', (trans_id,))
        tr = cur.fetchone()
        if not tr or tr['return_date'] is not None:
            flash('Invalid transaction.')
            conn.close()
            return redirect(url_for('transactions'))
        # compute fee: simple rule -> days late * rent_fee (assume 7-day free period)
        issue_dt = datetime.fromisoformat(tr['issue_date'])
        now = datetime.utcnow()
        days = (now - issue_dt).days
        grace = 7
        late_days = max(0, days - grace)
        # get rent_fee from book
        cur.execute('SELECT rent_fee FROM books WHERE id=?', (tr['book_id'],))
        b = cur.fetchone()
        rent_fee = b['rent_fee'] if b else 10.0
        fee = late_days * rent_fee
        # update transaction
        cur.execute('UPDATE transactions SET return_date=?, fee_charged=? WHERE id=?',
                    (now.isoformat(), fee, trans_id))
        # update book stock
        cur.execute('UPDATE books SET stock = stock + 1 WHERE id=?', (tr['book_id'],))
        # update member debt
        cur.execute('UPDATE members SET debt = debt + ? WHERE id=?', (fee, tr['member_id']))
        # cap: do not allow debt > 500 on return (still charge but flash warning)
        cur.execute('SELECT debt FROM members WHERE id=?', (tr['member_id'],))
        debt = cur.fetchone()['debt']
        conn.commit()
        conn.close()
        if debt > 500:
            flash(f'Book returned. Member debt is ₹{debt:.2f} — exceeds ₹500.')
        else:
            flash(f'Book returned. Fee charged: ₹{fee:.2f}')
        return redirect(url_for('transactions'))
    # GET: show outstanding transactions (not returned)
    cur.execute('SELECT t.id as tid, b.title, m.name, t.issue_date FROM transactions t JOIN books b ON b.id=t.book_id JOIN members m ON m.id=t.member_id WHERE t.return_date IS NULL')
    rows = cur.fetchall()
    conn.close()
    return render_template('return.html', trans=rows)

@app.route('/transactions')
def transactions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT t.*, b.title as book_title, m.name as member_name FROM transactions t LEFT JOIN books b ON b.id=t.book_id LEFT JOIN members m ON m.id=t.member_id ORDER BY t.id DESC')
    rows = cur.fetchall()
    conn.close()
    return render_template('transactions.html', trans=rows)

# Import from Frappe API
@app.route('/import', methods=['GET','POST'])
def import_books():
    if request.method == 'POST':
        title = request.form.get('title','')
        page = int(request.form.get('page') or 1)
        count = int(request.form.get('count') or 20)
        # API gives 20 books per page; we'll loop pages if count >20
        url = 'https://frappe.io/api/method/frappe-library'
        imported = 0
        conn = get_db()
        cur = conn.cursor()
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
                cur.execute('INSERT INTO books (title, authors, isbn, publisher, pages, stock) VALUES (?,?,?,?,?,?)',
                            (item.get('title'), item.get('authors'), item.get('isbn'), item.get('publisher'), item.get('num_pages') or 0, 1))
                imported += 1
                remaining -= 1
                if remaining <= 0:
                    break
            p += 1
        conn.commit()
        conn.close()
        flash(f'Imported {imported} books.')
        return redirect(url_for('books'))
    return render_template('import.html')

if __name__ == '__main__':
    app.run(debug=True)
