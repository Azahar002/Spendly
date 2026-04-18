# Spec: Login and Logout

## Overview
This step implements session-based authentication for Spendly. Users can submit their email and password via the login form; on success, their `user_id` and `name` are stored in a Flask session cookie. The logout route clears that session. This is the foundation that future protected routes (profile, expenses) will depend on — no route guard is added here, but the session is established so Step 4+ can check it.

## Depends on
- Step 01 — Database Setup (users table must exist)
- Step 02 — Registration (users must be able to create accounts)

## Routes
- `POST /login` — accepts email + password, verifies credentials, sets session, redirects to `/profile` on success or re-renders `login.html` with error — public
- `GET /logout` — clears the session and redirects to `/` — public

## Database changes
No database changes. The existing `users` table (with `id`, `email`, `password_hash`) is sufficient.

## Templates
- **Modify:** `templates/login.html` — add the POST form with email + password fields and an error message block (currently the template exists but the route is GET-only stub)

## Files to change
- `app.py` — convert `/login` to handle GET + POST; implement `/logout` to clear session and redirect
- `templates/login.html` — add `<form method="POST">` with email, password fields and error display

## Files to create
No new files.

## New dependencies
No new dependencies. `flask.session` is built-in; `werkzeug.security.check_password_hash` is already in `requirements.txt` via Werkzeug.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw SQLite via `get_db()` in `database/db.py`
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plaintext
- `app.secret_key` must be set before sessions work — add it after `app = Flask(__name__)`
- Use CSS variables — never hardcode hex values in templates or stylesheets
- All templates extend `base.html`
- Use `abort(405)` if an unexpected method reaches a route, not bare string returns
- Store only `user_id` and `name` in the session — never store the password hash
- After successful login redirect with `redirect(url_for("profile"))` — never hardcode the URL
- After logout redirect with `redirect(url_for("landing"))` — never hardcode the URL

## Definition of done
- [ ] Visiting `GET /login` renders the login form with email and password fields
- [ ] Submitting the form with a valid email + correct password sets the session and redirects to `/profile`
- [ ] Submitting with a valid email + wrong password re-renders `login.html` with an error message (no redirect)
- [ ] Submitting with an email that does not exist re-renders `login.html` with an error message
- [ ] Submitting with any empty field re-renders `login.html` with an error message
- [ ] Visiting `GET /logout` clears the session (`user_id` is no longer in `session`)
- [ ] After logout, the browser is redirected to the landing page `/`
- [ ] The demo user seeded in Step 01 (`demo@spendly.com` / `demo123`) can log in successfully
