import os
import secrets
from functools import wraps

import psycopg2
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute_query

APP_VERSION = "0.1.4"

app = Flask(__name__)


app.secret_key = os.environ["SECRET_KEY"]


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        user = execute_query(
            """
            SELECT id
            FROM users
            WHERE id = %s
            """,
            (session["user_id"],),
            fetch_one=True,
        )

        if not user:
            session.clear()
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("dashboard"))


@app.route("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@app.route("/create-account", methods=["GET"])
def create_account():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("create-account.html")


@app.route("/signup", methods=["GET"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("create-account.html")


@app.route("/signup", methods=["POST"])
def signup_page():
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]

    if len(password) < 8:
        flash(
            "Password must be at least 8 characters long.",
            "error",
        )
        return redirect(url_for("create_account"))

    existing_user = execute_query(
        """
        SELECT id
        FROM users
        WHERE email = %s
        """,
        (email,),
        fetch_one=True,
    )

    if existing_user:
        flash(
            "An account with this email already exists.",
            "error",
        )

        return redirect(url_for("create_account"))

    hashed_password = generate_password_hash(password)

    try:
        result = execute_query(
            """
            INSERT INTO users (name, password, email)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (username, hashed_password, email),
            returning=True,
        )
    except psycopg2.errors.UniqueViolation:
        flash(
            "An account with this email already exists.",
            "error",
        )
        return redirect(url_for("create_account"))

    user_id = result[0]

    session["user_id"] = user_id

    flash(
        "Account created successfully.",
        "success",
    )

    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET"])
def login():

    if "user_id" in session:

        user = execute_query(
            """
            SELECT id
            FROM users
            WHERE id = %s
            """,
            (session["user_id"],),
            fetch_one=True,
        )

        if user:
            return redirect(url_for("dashboard"))

        session.clear()

    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_post():
    email = request.form["email"]
    password = request.form["password"]

    user = execute_query(
        "SELECT id, name, email, password FROM users WHERE email = %s",
        (email,),
        fetch_one=True,
    )

    if user and check_password_hash(user[3], password):
        session["user_id"] = user[0]
        return redirect(url_for("dashboard"))

    return render_template(
        "login.html",
        error="Invalid email or password",
    )


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():

    user = execute_query(
        """
        SELECT name
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],),
        fetch_one=True,
    )

    return render_template(
        "dashboard.html",
        name=user[0],
    )


@app.route("/my-bookings")
@login_required
def my_bookings():

    rows = execute_query(
        """
        SELECT
            id,
            ticket_number,
            departure_state,
            arrival_state,
            departure_time,
            arrival_time,
            ticket_price,
            status
        FROM tickets
        WHERE user_id = %s
        ORDER BY departure_time
        """,
        (session["user_id"],),
        fetch_all=True,
    )

    bookings = [
        {
            "id": row[0],
            "ticket_number": row[1],
            "departure_state": row[2],
            "arrival_state": row[3],
            "departure_time": row[4],
            "arrival_time": row[5],
            "ticket_price": row[6],
            "status": row[7],
        }
        for row in rows
    ]

    return render_template(
        "my-bookings.html",
        bookings=bookings,
    )


@app.route("/cancel-booking/<int:ticket_id>", methods=["POST"])
@login_required
def cancel_booking(ticket_id):

    execute_query(
        """
        UPDATE tickets
        SET status = 'CANCELLED'
        WHERE id = %s
        AND user_id = %s
        """,
        (ticket_id, session["user_id"]),
    )

    return redirect("/my-bookings")


@app.route("/rebook/<int:ticket_id>", methods=["POST"])
@login_required
def rebook(ticket_id):

    execute_query(
        """
        UPDATE tickets
        SET status = 'CONFIRMED'
        WHERE id = %s
        AND user_id = %s
        """,
        (
            ticket_id,
            session["user_id"],
        ),
    )

    return redirect("/my-bookings")


@app.route("/book-flight", methods=["GET"])
@login_required
def book_flight():
    states = execute_query(
        "SELECT state_name FROM states ORDER BY state_name",
        fetch_all=True,
    )

    return render_template(
        "book-flight.html",
        states=states,
    )


@app.route("/book-flight/<int:flight_id>", methods=["POST"])
@login_required
def book_flight_post(flight_id):

    flight = execute_query(
        """
        SELECT
            departure_state,
            arrival_state,
            departure_time,
            arrival_time,
            price
        FROM flights
        WHERE id = %s
        """,
        (flight_id,),
        fetch_one=True,
    )

    if not flight:
        return "Flight not found", 404

    ticket_number = f"FB{secrets.randbelow(900000) + 100000}"

    execute_query(
        """
        INSERT INTO tickets
        (
            ticket_number,
            departure_state,
            arrival_state,
            departure_time,
            arrival_time,
            ticket_price,
            user_id,
            status
        )
        VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            ticket_number,
            flight[0],
            flight[1],
            flight[2],
            flight[3],
            flight[4],
            session["user_id"],
            "CONFIRMED",
        ),
    )

    return redirect("/my-bookings")


@app.route("/find-flights", methods=["GET", "POST"])
@login_required
def find_flights():

    if request.method == "POST":

        departure_state = request.form["departure_state"]
        arrival_state = request.form["arrival_state"]
        departure_time = request.form["departure_time"]

        flights = execute_query(
            """
            SELECT 
                id,
                departure_state,
                arrival_state,
                departure_time,
                arrival_time,
                price
            FROM flights
            WHERE departure_state = %s
            AND arrival_state = %s
            AND departure_time::date >= %s
            ORDER BY departure_time
            """,
            (
                departure_state,
                arrival_state,
                departure_time,
            ),
            fetch_all=True,
        )

        return render_template(
            "find-flights.html",
            flights=flights,
        )

    return render_template("find-flights.html")


@app.route("/account-settings", methods=["GET"])
@login_required
def account_settings():

    row = execute_query(
        """
        SELECT name, email
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],),
        fetch_one=True,
    )

    if not row:
        session.clear()
        return redirect(url_for("login"))

    user = {
        "name": row[0],
        "email": row[1],
    }

    return render_template(
        "account-settings.html",
        user=user,
    )


@app.route("/account-settings", methods=["POST"])
@login_required
def account_settings_post():

    name = request.form["name"].strip()
    email = request.form["email"].strip()

    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    stored_password = execute_query(
        """
        SELECT password
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],),
        fetch_one=True,
    )[0]

    existing_user = execute_query(
        """
        SELECT id
        FROM users
        WHERE email = %s
        AND id <> %s
        """,
        (email, session["user_id"]),
        fetch_one=True,
    )

    if existing_user:
        return render_template(
            "account-settings.html",
            user={
                "name": name,
                "email": email,
            },
            error="Email address already exists.",
        )

    if current_password or new_password or confirm_password:

        if not new_password:
            flash(
                "New password cannot be empty.",
                "error",
            )
            return redirect(url_for("account_settings"))

        if not check_password_hash(stored_password, current_password):
            flash(
                "Current password is incorrect.",
                "error",
            )
            return redirect(url_for("account_settings"))

        if new_password != confirm_password:
            flash(
                "New passwords do not match.",
                "error",
            )
            return redirect(url_for("account_settings"))

        if len(new_password) < 8:
            flash(
                "Password must be at least 8 characters long.",
                "error",
            )

            return redirect(url_for("account_settings"))

        execute_query(
            """
            UPDATE users
            SET
                name = %s,
                email = %s,
                password = %s
            WHERE id = %s
            """,
            (
                name,
                email,
                generate_password_hash(new_password),
                session["user_id"],
            ),
        )

    else:

        execute_query(
            """
            UPDATE users
            SET
                name = %s,
                email = %s
            WHERE id = %s
            """,
            (
                name,
                email,
                session["user_id"],
            ),
        )

    flash(
        "Your account details have been updated successfully.",
        "success",
    )
    return redirect(url_for("account_settings"))


@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():

    delete_password = request.form["delete_password"]

    user = execute_query(
        """
        SELECT password
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],),
        fetch_one=True,
    )

    if not user:
        session.clear()
        return redirect(url_for("login"))

    stored_password = user[0]

    if not check_password_hash(stored_password, delete_password):

        flash(
            "Incorrect password. Account was not deleted.",
            "error",
        )

        return redirect(url_for("account_settings"))

    execute_query(
        """
        DELETE FROM users
        WHERE id = %s
        """,
        (session["user_id"],),
    )

    session.clear()

    flash(
        "Your account has been deleted successfully.",
        "success",
    )

    return redirect(url_for("create_account"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
