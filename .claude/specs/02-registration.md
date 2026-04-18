# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account. This step wires up the `POST /register` route to validate form input, hash the password, insert the user into the database, and redirect on success. The `GET /register` route already renders `register.html`; this step makes the form functional. Registration is the first authentication step and is required before login (Step 3) can work.

## Depends on
- Step 1 — Database Setup (`get_db()`, `init_db()`, `users` table must exist)

## Routes
- `POST /register` — validates form data, creates user account, redirects to login — public

## Database changes
No new tables or columns. The `users` table (created in Step 1) already has all required columns: `id`, `name`, `email`, `password_hash`, `created_at`.

A new helper function `create_user(name, email, password_hash)` must be added to `database/db.py`.

## Templates
- **Modify:** `templates/register.html` — add `method="POST"` and `action="{{ url_for('register') }}"` to the `<form>` tag; add `name` attributes to all inputs; display flash messages for errors and success

## Files to change
- `app.py` — add `POST` method to the `/register` route; import `request`, `redirect`, `url_for`, `flash`, `session` from flask; import `create_user` and `get_user_by_email` from `database/db`; implement registration logic
- `database/db.py` — add `create_user(name, email, password_hash)` and `get_user_by_email(email)` helpers
- `templates/register.html` — wire up the form (method, action, input names, flash messages)
- `app.py` — set `app.secret_key` (required for `flash()` to work)

## Files to create
No new files.

## New dependencies
No new dependencies. `werkzeug.security` is already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — no f-strings in SQL
- Hash passwords with `werkzeug.security.generate_password_hash` before inserting
- Never store plaintext passwords
- Use `flash()` for all user-facing error and success messages
- Use `abort()` for unexpected server errors, not bare string returns
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- Redirect to `GET /login` on successful registration (Post/Redirect/Get pattern)
- Validate on the server: name, email, and password are all required; email must be unique; password must be at least 8 characters
- `create_user` and `get_user_by_email` belong in `database/db.py`, not in the route
- `app.secret_key` must be set before `flash()` will work — use a hard-coded dev string for now (e.g. `"dev-secret-change-me"`)

## Definition of done
- [ ] Submitting the form with valid data creates a new row in the `users` table with a hashed password
- [ ] Submitting with a duplicate email shows an error flash message and does not insert a second row
- [ ] Submitting with a missing name, email, or password shows an error flash message
- [ ] Submitting with a password shorter than 8 characters shows an error flash message
- [ ] Successful registration redirects the user to `GET /login`
- [ ] Flash messages are visible in the template
- [ ] Passwords in the database are hashed (not plaintext)
- [ ] App starts without errors
- [ ] No DB logic lives in the route function
