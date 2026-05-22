from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_TABLES = {"users", "movies", "checkouts"}

app = Flask(__name__)
app.config["DATABASE"] = str(BASE_DIR / "database.db")


def database_path() -> Path:
    return Path(app.config["DATABASE"])


def connect_db(path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(path or database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(_: BaseException | None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def ensure_database() -> None:
    path = database_path()
    connection = connect_db(path)
    try:
        existing_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not REQUIRED_TABLES.issubset(existing_tables):
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            connection.executescript(schema)
            connection.commit()
    finally:
        connection.close()


def get_request_data() -> dict[str, Any]:
    if request.is_json:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            return payload
    if request.form:
        return request.form.to_dict()
    return {}


def pick_value(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return None


def pick_query_value(*keys: str) -> Any:
    for key in keys:
        if key in request.args:
            return request.args.get(key)
    return None


def json_error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def parse_positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {label}.") from None
    if parsed < 1:
        raise ValueError(f"Invalid {label}.")
    return parsed


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def validate_person_name(value: Any, label: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        raise ValueError(f"{label} is required.")
    return cleaned


def validate_email(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        raise ValueError("Email is required.")
    if not EMAIL_PATTERN.match(cleaned):
        raise ValueError("Please enter a valid email address.")
    return cleaned


def validate_movie_title(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        raise ValueError("Movie title cannot be blank.")
    return cleaned


def serialize_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "firstName": row["firstName"],
        "lastName": row["lastName"],
        "email": row["email"],
    }


def serialize_checkout(row: sqlite3.Row) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "userId": row["userId"],
        "movieId": row["movieId"],
        "title": row["title"],
    }
    if "firstName" in row.keys():
        payload["firstName"] = row["firstName"]
        payload["lastName"] = row["lastName"]
        payload["email"] = row["email"]
    return payload


def serialize_movie(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "inStock": row["inStock"],
        "checkedOut": row["checkedOut"],
        "available": row["available"],
    }


def fetch_user_by_id(user_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        "SELECT id, firstName, lastName, email FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def fetch_user_by_email(email: str) -> sqlite3.Row | None:
    return get_db().execute(
        "SELECT id, firstName, lastName, email FROM users WHERE email = ?",
        (email,),
    ).fetchone()


def fetch_movie(movie_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        "SELECT id, title, inStock FROM movies WHERE id = ?",
        (movie_id,),
    ).fetchone()


def query_movies() -> list[dict[str, Any]]:
    rows = get_db().execute(
        """
        SELECT
            movies.id,
            movies.title,
            movies.inStock,
            COALESCE(counts.checkedOut, 0) AS checkedOut,
            movies.inStock - COALESCE(counts.checkedOut, 0) AS available
        FROM movies
        LEFT JOIN (
            SELECT movieId, COUNT(*) AS checkedOut
            FROM checkouts
            GROUP BY movieId
        ) AS counts
            ON counts.movieId = movies.id
        ORDER BY LOWER(movies.title), movies.title
        """
    ).fetchall()
    return [serialize_movie(row) for row in rows]


def fetch_movie_stats(movie_id: int) -> dict[str, Any] | None:
    rows = get_db().execute(
        """
        SELECT
            movies.id,
            movies.title,
            movies.inStock,
            COALESCE(counts.checkedOut, 0) AS checkedOut,
            movies.inStock - COALESCE(counts.checkedOut, 0) AS available
        FROM movies
        LEFT JOIN (
            SELECT movieId, COUNT(*) AS checkedOut
            FROM checkouts
            GROUP BY movieId
        ) AS counts
            ON counts.movieId = movies.id
        WHERE movies.id = ?
        """,
        (movie_id,),
    ).fetchone()
    if rows is None:
        return None
    return serialize_movie(rows)


def query_checkouts(
    user_id: int | None = None, movie_id: int | None = None
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            checkouts.id,
            checkouts.userId,
            checkouts.movieId,
            movies.title,
            users.firstName,
            users.lastName,
            users.email
        FROM checkouts
        INNER JOIN movies ON movies.id = checkouts.movieId
        INNER JOIN users ON users.id = checkouts.userId
    """
    where_clauses: list[str] = []
    params: list[Any] = []
    if user_id is not None:
        where_clauses.append("checkouts.userId = ?")
        params.append(user_id)
    if movie_id is not None:
        where_clauses.append("checkouts.movieId = ?")
        params.append(movie_id)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY LOWER(movies.title), movies.title"
    rows = get_db().execute(sql, params).fetchall()
    return [serialize_checkout(row) for row in rows]


def user_checkout_count(user_id: int) -> int:
    row = get_db().execute(
        "SELECT COUNT(*) AS total FROM checkouts WHERE userId = ?",
        (user_id,),
    ).fetchone()
    return int(row["total"])


def user_has_movie(user_id: int, movie_id: int) -> bool:
    row = get_db().execute(
        "SELECT id FROM checkouts WHERE userId = ? AND movieId = ?",
        (user_id, movie_id),
    ).fetchone()
    return row is not None


@app.route("/")
def home():
    ensure_database()
    return render_template("home.html")


@app.route("/account/")
def account():
    ensure_database()
    return render_template("account.html")


@app.route("/movie/")
def movie():
    ensure_database()
    return render_template("movie.html")


@app.route("/rent/")
def rent():
    ensure_database()
    return render_template("rent.html")


@app.route("/dbUser/", methods=["GET", "POST"])
def db_user():
    ensure_database()
    connection = get_db()

    if request.method == "GET":
        try:
            email = validate_email(pick_query_value("email"))
        except ValueError as exc:
            return json_error(str(exc), 400)

        user = fetch_user_by_email(email)
        if user is None:
            return json_error("No account found for that email.", 404)
        return jsonify(serialize_user(user))

    data = get_request_data()
    try:
        first_name = validate_person_name(
            pick_value(data, "firstName", "first_name"), "First name"
        )
        last_name = validate_person_name(
            pick_value(data, "lastName", "last_name"), "Last name"
        )
        email = validate_email(pick_value(data, "email"))
    except ValueError as exc:
        return json_error(str(exc), 400)

    try:
        cursor = connection.execute(
            """
            INSERT INTO users (firstName, lastName, email)
            VALUES (?, ?, ?)
            """,
            (first_name, last_name, email),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        return json_error("An account with that email already exists.", 409)

    user = connection.execute(
        "SELECT id, firstName, lastName, email FROM users WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify(serialize_user(user)), 201


@app.route("/dbMovie/", methods=["GET", "POST"])
def db_movie():
    ensure_database()
    connection = get_db()

    if request.method == "GET":
        return jsonify(query_movies())

    data = get_request_data()
    action = clean_text(pick_value(data, "action")).lower()
    if action not in {"new", "add", "remove"}:
        return json_error("Invalid movie action.", 400)

    if action == "new":
        try:
            title = validate_movie_title(pick_value(data, "title"))
        except ValueError as exc:
            return json_error(str(exc), 400)

        try:
            connection.execute(
                "INSERT INTO movies (title, inStock) VALUES (?, 1)",
                (title,),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            return json_error("That movie already exists in the catalog.", 409)
        return jsonify(query_movies())

    try:
        movie_id = parse_positive_int(
            pick_value(data, "movieId", "movie_id", "id"), "movie ID"
        )
    except ValueError as exc:
        return json_error(str(exc), 400)

    movie_row = fetch_movie(movie_id)
    if movie_row is None:
        return json_error("Movie not found.", 404)

    if action == "add":
        connection.execute(
            "UPDATE movies SET inStock = inStock + 1 WHERE id = ?",
            (movie_id,),
        )
        connection.commit()
        return jsonify(query_movies())

    movie_stats = fetch_movie_stats(movie_id)
    if movie_stats is None:
        return json_error("Movie not found.", 404)
    if movie_stats["inStock"] <= 0:
        return json_error("Stock cannot go below 0.", 409)
    if movie_stats["inStock"] <= movie_stats["checkedOut"]:
        return json_error(
            "Cannot reduce stock below the number currently checked out.", 409
        )

    connection.execute(
        "UPDATE movies SET inStock = inStock - 1 WHERE id = ?",
        (movie_id,),
    )
    connection.commit()
    return jsonify(query_movies())


@app.route("/dbRent/", methods=["GET", "POST"])
def db_rent():
    ensure_database()
    connection = get_db()

    if request.method == "GET":
        raw_user_id = pick_query_value("userId", "user_id")
        raw_movie_id = pick_query_value("movieId", "movie_id")

        try:
            user_id = (
                parse_positive_int(raw_user_id, "user ID")
                if raw_user_id is not None
                else None
            )
            movie_id = (
                parse_positive_int(raw_movie_id, "movie ID")
                if raw_movie_id is not None
                else None
            )
        except ValueError as exc:
            return json_error(str(exc), 400)

        if user_id is not None and fetch_user_by_id(user_id) is None:
            return json_error("User not found.", 404)
        if movie_id is not None and fetch_movie(movie_id) is None:
            return json_error("Movie not found.", 404)

        return jsonify(query_checkouts(user_id=user_id, movie_id=movie_id))

    data = get_request_data()
    action = clean_text(pick_value(data, "action")).lower()
    if action not in {"rent", "return"}:
        return json_error("Invalid rental action.", 400)

    try:
        user_id = parse_positive_int(
            pick_value(data, "userId", "user_id"), "user ID"
        )
        movie_id = parse_positive_int(
            pick_value(data, "movieId", "movie_id"), "movie ID"
        )
    except ValueError as exc:
        return json_error(str(exc), 400)

    user = fetch_user_by_id(user_id)
    if user is None:
        return json_error("User not found.", 404)

    movie = fetch_movie(movie_id)
    if movie is None:
        return json_error("Movie not found.", 404)

    if action == "rent":
        if user_checkout_count(user_id) >= 3:
            return json_error("A member may only rent up to 3 movies.", 409)
        if user_has_movie(user_id, movie_id):
            return json_error("This member already has that movie checked out.", 409)

        movie_stats = fetch_movie_stats(movie_id)
        if movie_stats is None:
            return json_error("Movie not found.", 404)
        if movie_stats["available"] <= 0:
            return json_error("That movie is currently unavailable.", 409)

        connection.execute(
            "INSERT INTO checkouts (userId, movieId) VALUES (?, ?)",
            (user_id, movie_id),
        )
        connection.commit()
        return jsonify(query_checkouts(user_id=user_id))

    cursor = connection.execute(
        "DELETE FROM checkouts WHERE userId = ? AND movieId = ?",
        (user_id, movie_id),
    )
    connection.commit()
    if cursor.rowcount == 0:
        return json_error("That movie is not currently checked out by this member.", 404)

    return jsonify(query_checkouts(user_id=user_id))


ensure_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
