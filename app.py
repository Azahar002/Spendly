from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.")
        if get_user_by_email(email) is not None:
            return render_template("register.html", error="An account with that email already exists.")

        create_user(name, email, generate_password_hash(password))
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="All fields are required.")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Alex Johnson",
        "email": "alex@example.com",
        "member_since": "January 2026",
        "initials": "AJ",
    }
    stats = {
        "total_spent": 264.25,
        "tx_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "Apr 18, 2026", "description": "Grocery run",     "category": "Food",          "amount": 18.75},
        {"date": "Apr 15, 2026", "description": "Miscellaneous",    "category": "Other",         "amount": 5.00},
        {"date": "Apr 12, 2026", "description": "New shirt",        "category": "Shopping",      "amount": 60.00},
        {"date": "Apr 10, 2026", "description": "Cinema tickets",   "category": "Entertainment", "amount": 20.00},
        {"date": "Apr 08, 2026", "description": "Pharmacy",         "category": "Health",        "amount": 45.00},
    ]
    categories = [
        {"name": "Bills",         "total": 95.00, "pct": 36},
        {"name": "Shopping",      "total": 60.00, "pct": 23},
        {"name": "Health",        "total": 45.00, "pct": 17},
        {"name": "Food",          "total": 31.25, "pct": 12},
        {"name": "Entertainment", "total": 20.00, "pct":  8},
        {"name": "Transport",     "total":  8.00, "pct":  3},
        {"name": "Other",         "total":  5.00, "pct":  2},
    ]
    return render_template(
        "profile.html",
        user=user, stats=stats,
        transactions=transactions, categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
