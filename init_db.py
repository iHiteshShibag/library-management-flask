
import sqlite3
conn = sqlite3.connect('library.db')
c = conn.cursor()
c.executescript("""
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS books;
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    authors TEXT,
    isbn TEXT,
    publisher TEXT,
    pages INTEGER,
    stock INTEGER DEFAULT 0,
    rent_fee REAL DEFAULT 10.0
);
CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    debt REAL DEFAULT 0
);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    member_id INTEGER,
    issue_date TEXT,
    return_date TEXT,
    fee_charged REAL DEFAULT 0
);
""")
# sample data
c.execute("INSERT INTO books (title, authors, stock, rent_fee) VALUES (?,?,?,?)", ('The Alchemist', 'Paulo Coelho', 3, 5.0))
c.execute("INSERT INTO books (title, authors, stock, rent_fee) VALUES (?,?,?,?)", ('Harry Potter and the Sorcerer\'s Stone', 'J.K. Rowling', 2, 8.0))
c.execute("INSERT INTO members (name, phone) VALUES (?,?)", ('Raj Kumar', '9876543210'))
c.execute("INSERT INTO members (name, phone) VALUES (?,?)", ('Priya Singh', '9123456780'))
conn.commit()
conn.close()
print('Initialized library.db with sample data.')
