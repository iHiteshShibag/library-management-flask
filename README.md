# 📚 LibraryOS — Library Management System

A **Library Management Web Application** built with **Flask**, **PostgreSQL**, and **Tailwind CSS** — role-based staff accounts, and a full book/member/loan workflow with fines, reservations, audit logging, a REST API, and a dashboard.

> **Setup on Windows?** See [`Setup_and_Configuration_Guide.pdf`](Setup_and_Configuration_Guide.pdf) in this folder for a full walkthrough with Windows-specific commands (PowerShell venv activation, Task Scheduler instead of cron, a Windows-compatible production server, etc.) — a few things below (Gunicorn, `cp`, cron) are Linux/macOS-specific.

---

## 🚀 Features

### 🔐 Accounts & organization
- Single-org mode: the very first signup founds the organization and becomes its admin; every signup after that just joins that same org as staff (mirrored by `flask create-admin` on the CLI)
- Login/logout, forgot/reset password by email link, change password
- Admin and staff roles, enforced both in the UI and server-side
- Admins can invite additional users directly as admin or staff, and manage them from Settings
- Per-user API keys for the REST API (generate/regenerate/revoke from your profile)

### 📖 Book management
- Add, edit, delete, and search books (by title/author)
- Import books in bulk from the Frappe Library API, with automatic ISBN de-duplication against your existing catalog (response keys are normalized first — the API's own JSON has inconsistent whitespace in field names)
- CSV export
- Pagination

### 👥 Member management
- Register, view, and remove members (name, phone, email)
- CSV export
- Pagination

### 🔄 Issue, return & reservations
- Issue books to members and return them, with race-safe atomic stock/return updates under concurrent use
- Automatic overdue fine calculation (7-day grace period, then per-day rent fee)
- Members over ₹500 in outstanding debt are blocked from new issues
- Reservation/hold queue for books, with automatic fulfillment when a held book is issued to the member who reserved it
- Transaction history with CSV export and pagination

### 🔔 Reminders
- `flask send-due-reminders` CLI command emails members whose loans are approaching or past the grace period (run it from cron or another external scheduler — the app has no built-in job runner)
- Emails are sent via SMTP if configured (`EMAIL_USER`/`EMAIL_PASSWORD` in `.env`); otherwise they're logged/flashed instead, so the app still works out of the box in development

### 📊 Dashboard & audit log
- Stats: book titles, copies, members, active loans, overdue count, outstanding fines
- Charts: books by author, borrowing trend, fines collected, stock overview (last 8 weeks)
- Top borrowed books/authors, recent activity feed
- Admin-only audit log of who created/edited/deleted what and when

### 🌐 REST API
- `GET/POST /api/v1/books`, `GET/PATCH/DELETE /api/v1/books/<id>`
- `GET/POST /api/v1/members`
- `GET /api/v1/transactions`, `POST /api/v1/issue`, `POST /api/v1/return`
- `GET /api/v1/me`
- Authenticate with `Authorization: Bearer <api_key>` (generate a key from your profile settings)

### 🛡️ Security
- CSRF protection on all state-changing form submissions
- Rate limiting on login/signup/forgot-password to slow down brute-force and abuse (in-memory by default; point `RATELIMIT_STORAGE_URI` at Redis if running multiple worker processes)
- Session cookies with `HttpOnly`/`SameSite=Lax`, and `Secure` once `SESSION_COOKIE_SECURE=true` is set behind HTTPS
- Minimum password length enforced server-side
- Passwords hashed with Werkzeug's `generate_password_hash`

### 🩺 Operations
- `GET /healthz` — liveness check (verifies the DB connection), suitable for a load balancer or orchestrator
- Branded 404/500 error pages instead of Flask's bare defaults
- Optional Sentry error tracking — set `SENTRY_DSN` to enable; unset, it's skipped entirely
- `pytest` smoke suite covering signup/login, book/member/issue-return flows, role enforcement, and the REST API (see step 9 below)

### 🎨 User interface
- Responsive Tailwind design with dark/light mode
- Animated dashboard, page transitions (GSAP + Lenis)
- Collapsible sidebar — collapsing fully hides it (rather than shrinking to an icon rail); a floating logo badge takes its place and re-expands it on click. State persists in `localStorage`.

---

## 🛠️ Tech stack

| Technology | Purpose |
|------------|----------|
| Python / Flask | Backend & routing |
| PostgreSQL | Database |
| Flask-SQLAlchemy / Flask-Migrate | ORM & schema migrations |
| Flask-Login | Sessions & auth |
| Flask-WTF | CSRF protection |
| Flask-Limiter | Rate limiting |
| Tailwind CSS, GSAP, Chart.js | Frontend & charts |
| Jinja2 | Templating |
| Requests | Frappe Library API integration |

---

## 📂 Project structure

```text
library-management-flask/
│
├── app.py              # App factory / blueprint registration
├── config.py           # Env-driven configuration
├── db.py               # SQLAlchemy + Migrate setup
├── extensions.py       # Shared extension instances (login, csrf, limiter)
├── models.py           # Organization, User, Book, Member, Transaction, Reservation, AuditLog
├── auth.py             # Signup/login/logout, forgot/reset password
├── books.py            # Book CRUD, search, CSV export, Frappe import
├── members.py          # Member CRUD, CSV export
├── transactions.py     # Issue/return, transaction history, CSV export
├── reservations.py     # Hold queue
├── audit.py             # Audit log helper + admin view
├── settings.py         # Profile, change password, API key, user management
├── api.py               # REST API (API-key authenticated)
├── mailer.py            # SMTP email helper with a dev-mode fallback
├── reminders.py          # `flask send-due-reminders` CLI command
├── migrations/          # Alembic migrations
├── static/               # CSS/JS
└── templates/            # Jinja2 templates
```

---

## ⚙️ Installation & setup

### 1. Clone and enter the repo
```bash
git clone https://github.com/iHiteshShibag/library-management-flask.git
cd library-management-flask
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
```
Then edit `.env`:
- `SECRET_KEY` — generate one with `python -c "import secrets; print(secrets.token_hex(32))"`
- `DATABASE_URL` — a PostgreSQL connection string
- `EMAIL_USER` / `EMAIL_PASSWORD` / `EMAIL_SMTP_HOST` / `EMAIL_SMTP_PORT` — optional, for real password-reset and reminder emails; without them the app logs/flashes them instead

### 5. Run database migrations
```bash
flask db upgrade
```

### 6. Run the app

For local development:
```bash
python app.py
```

For anything beyond your own laptop, use a real WSGI server — `python app.py` / `flask run` is Werkzeug's dev server, which prints its own warning that it isn't meant for production traffic:
```bash
gunicorn app:app --workers 4
```
A `Procfile` (`web: gunicorn app:app`) is included for PaaS providers (Render, Heroku, etc.) that read it automatically. Behind Gunicorn, put a reverse proxy (Nginx, Caddy, or your platform's built-in one) in front to terminate TLS — Gunicorn itself doesn't speak HTTPS. A minimal Nginx snippet:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.example;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Once you're serving over HTTPS, set `SESSION_COOKIE_SECURE=true` in `.env` (see step 4) — it defaults to `false` so login doesn't break over plain `http://` in local dev. If you ever run more than one worker process, also point `RATELIMIT_STORAGE_URI` at a shared store like Redis instead of the default in-memory one, or each worker enforces its own separate rate limit.

> **Windows:** Gunicorn doesn't run there at all (it relies on `os.fork`, which Windows doesn't have). Use `waitress` instead (`pip install waitress`, then `waitress-serve --port=8000 app:app`), or run the whole app inside WSL2/Docker for parity with the Linux instructions above. See the PDF guide linked at the top of this file for the full walkthrough.

### 7. Open your browser
```text
http://127.0.0.1:5000
```
Sign up to create your organization and admin account, or use `flask create-admin` to create one from the CLI.

### 8. (Optional) Schedule due-date reminders
Add a daily cron entry (or equivalent) to run:
```bash
flask send-due-reminders
```

### 9. (Optional) Run the test suite
```bash
pip install -r requirements-dev.txt
```
Tests run against a real Postgres database (not SQLite — the dashboard's analytics queries use Postgres-only SQL like `date_trunc`, so SQLite would silently skip over real dialect bugs). Create a dedicated test database once:
```sql
CREATE DATABASE library_test OWNER library;
```
Then run:
```bash
pytest
```
It defaults to `postgresql://library:library_dev_pw@localhost:5432/library_test` — override with `TEST_DATABASE_URL` if your setup differs.

---

## ✅ Before deploying to production

The defaults above are tuned for local development. Before this is reachable by real users:

- [ ] **Serve it with Gunicorn behind a reverse proxy over HTTPS** — see step 6 above. Don't run `python app.py` / `flask run` in production; it's Werkzeug's dev server and says so itself.
- [ ] **Set `SESSION_COOKIE_SECURE=true`** once HTTPS is in front of the app (leave it `false` until then, or login will silently break).
- [ ] **Generate fresh secrets for this environment** — don't reuse the `SECRET_KEY` or Postgres password from your local `.env`/docker-compose. A leaked local dev secret is low-stakes; the same value reused in production is a real credential. Generate a new one with `python -c "import secrets; print(secrets.token_hex(32))"` and use a strong, unique Postgres password for the production database.
- [ ] **Configure real email delivery** — set `EMAIL_USER`/`EMAIL_PASSWORD` (and `EMAIL_SMTP_HOST`/`EMAIL_SMTP_PORT` if not using Gmail) to an account or transactional provider (SendGrid, Mailgun, SES, etc. all speak SMTP) you control. Without this, password-reset links and due-date reminders only get logged/flashed to the screen instead of actually emailed — fine for solo local testing, not for real users who forget their password.
- [ ] **Point `RATELIMIT_STORAGE_URI` at Redis** if running more than one Gunicorn worker — the in-memory default tracks limits per-worker, not globally, so it under-enforces with `--workers > 1`.
- [ ] **Set `SENTRY_DSN`** (optional) if you want unhandled exceptions reported somewhere instead of only appearing in server logs.

---

## 🗄️ Database overview

| Table | Purpose |
|---------|---------|
| `organizations` | A single row — the org created by the first signup (see single-org mode above) |
| `users` | Staff/admin logins, scoped to an organization |
| `books` | Catalog, scoped to an organization |
| `members` | Library patrons, scoped to an organization |
| `transactions` | Issue/return history and fines |
| `reservations` | Hold queue on books |
| `audit_logs` | Who did what, and when |

All tables (other than `organizations`) carry an `org_id` foreign key, and every query in the app is scoped by the current user's organization.

---

## 🌐 External API integration

Books can be bulk-imported from the **Frappe Library API** (`/import`). Imports are capped at 200 books per request and skip titles whose ISBN already exists in your catalog.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m "Added new feature"`
4. Push the branch: `git push origin feature-name`
5. Open a pull request

---

## 📜 License

MIT — free to use, modify, and distribute for educational and personal purposes.

---

## 👨‍💻 Author

**Hitesh Shibag** — [GitHub](https://github.com/iHiteshShibag)

If you found this project helpful, consider giving it a ⭐ on GitHub.
