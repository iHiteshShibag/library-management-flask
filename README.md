# Library Management Web App (Flask)
This is a beginner-friendly Library Management application built with Flask and SQLite.

# Features
- CRUD for Books and Members
- Issue and Return books
- Charge fees on late returns (7-day grace period)
- Import books from Frappe Library API
- Simple Bootstrap-based UI

# Run locally
cd library_app
pip install -r requirements.txt
python init_db.py
python app.py
Open http://127.0.0.1:5000 in your browser. 
