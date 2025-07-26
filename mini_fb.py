"""
A minimal social network web application built with Flask and SQLite.

Features:

* User registration and login using a simple username/password hash stored in SQLite.
* Authenticated users can create posts, comment on posts and react with emojis.
* Anonymous users can browse the feed but must register/login to participate.
* Reactions are tied to the logged in user and each user can react with a given
  emoji on a post only once thanks to a composite UNIQUE constraint.

This module can be run directly with ``python mini_fb.py`` which will start
the Flask development server.
"""

from __future__ import annotations

import datetime
import hashlib
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Callable, Optional

from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Path to the SQLite database file.  If you deploy this on a platform like
# Render, place the DB on a persistent disk to keep data across restarts.
DB_PATH = Path(__file__).with_name("mini_fb.db")

app = Flask(__name__)
app.secret_key = "change-me-to-a-random-secret"  # Override in production via env var


def get_db() -> sqlite3.Connection:
    """Return a new database connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialise the SQLite database with required tables."""
    conn = get_db()
    # Create users table.  Passwords are stored as SHA256 hashes.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        );
        """
    )
    # Posts table: each post has an auto‑incrementing ID, the author,
    # body and timestamp (UTC ISO format).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT,
            body TEXT,
            created TEXT,
            FOREIGN KEY(author) REFERENCES users(username) ON DELETE CASCADE
        );
        """
    )
    # Comments table: each comment belongs to a post and has its own author.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            author TEXT,
            body TEXT,
            created TEXT,
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY(author) REFERENCES users(username) ON DELETE CASCADE
        );
        """
    )
    # Reactions table: composite unique constraint prevents a user from
    # reacting with the same emoji more than once on the same post.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reactions (
            post_id INTEGER,
            author TEXT,
            emoji TEXT,
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY(author) REFERENCES users(username) ON DELETE CASCADE,
            UNIQUE(post_id, author, emoji)
        );
        """
    )
    conn.commit()
    conn.close()


def load_logged_in_user() -> None:
    """Load the current logged‑in user into ``g.user`` before each request."""
    username = session.get("username")
    if username is None:
        g.user = None
    else:
        conn = get_db()
        user = conn.execute(
            "SELECT username FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()
        g.user = user["username"] if user else None


def login_required(view: Callable) -> Callable:
    """Decorator that redirects anonymous users to the login page."""

    @wraps(view)
    def wrapped_view(**kwargs):
        if getattr(g, "user", None) is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


init_db()
app.before_request(load_logged_in_user)


# -----------------------------------------------------------------------------
# HTML templates (Jinja2 strings) — in production you'd use template files
# -----------------------------------------------------------------------------

BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{{ title if title else 'Mini FB' }}</title>
    <style>
    body { font-family: sans-serif; max-width: 800px; margin: auto; padding: 1rem; }
    h1 { margin-top: 1.5rem; }
    form { margin-bottom: 1rem; }
    .error { color: red; }
    .post { border-bottom: 1px solid #ccc; padding-bottom: 1rem; margin-bottom: 1rem; }
    .comments { margin-left: 1rem; }
    .comment { font-size: 0.9rem; }
    </style>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
"""


@app.route("/")
def home() -> str:
    """Render the feed page, showing posts, comments and reactions."""
    conn = get_db()
    posts = conn.execute(
        "SELECT id, author, body, created FROM posts ORDER BY datetime(created) DESC"
    ).fetchall()
    # Gather comments keyed by post_id
    comments: dict[int, list[sqlite3.Row]] = {}
    for c in conn.execute(
        "SELECT id, post_id, author, body, created FROM comments ORDER BY datetime(created)"
    ).fetchall():
        comments.setdefault(c["post_id"], []).append(c)
    # Gather reactions counts keyed by post_id
    reactions: dict[int, dict[str, int]] = {}
    for r in conn.execute(
        "SELECT post_id, emoji, COUNT(*) as count FROM reactions GROUP BY post_id, emoji"
    ).fetchall():
        reactions.setdefault(r["post_id"], {})[r["emoji"]] = r["count"]
    conn.close()
    return render_template_string(
        BASE_TEMPLATE
        + """
{% block content %}
  <h1>Mini FB</h1>

  {% if g.user %}
    <p>Logged in as <strong>{{ g.user }}</strong> — <a href="{{ url_for('logout') }}">Logout</a></p>
    <!-- Post form -->
    <form action="{{ url_for('add') }}" method="post">
      <textarea name="body" placeholder="What's on your mind?" required></textarea><br>
      <button type="submit">Post</button>
    </form>
  {% else %}
    <p>You are browsing anonymously. <a href="{{ url_for('login') }}">Login</a> or <a href="{{ url_for('register') }}">Register</a> to participate.</p>
  {% endif %}

  <!-- Feed -->
  {% for p in posts %}
    <div class="post">
      <strong>{{ p.author }}</strong> <small>{{ p.created }}</small>
      <p>{{ p.body }}</p>
      <!-- Reactions -->
      <div>
        {% for emoji in ['👍','❤️'] %}
          <form action="{{ url_for('react', post_id=p.id) }}" method="post" style="display:inline">
            <button name="emoji" value="{{ emoji }}"{% if not g.user %} disabled{% endif %}>{{ emoji }}</button>
          </form>
        {% endfor %}
        {% set reacts = reactions.get(p.id) or {} %}
        {% for e, c in reacts.items() %}
          {{ e }}{{ c }}
        {% endfor %}
      </div>
      <!-- Comment form -->
      {% if g.user %}
        <form action="{{ url_for('comment', post_id=p.id) }}" method="post" class="comment">
          <input name="body" placeholder="Comment" required>
          <button type="submit">💬</button>
        </form>
      {% endif %}
      <!-- Existing comments -->
      <div class="comments">
        {% for c in comments.get(p.id) or [] %}
          <div class="comment">
            <small><strong>{{ c.author }}</strong>: {{ c.body }} ({{ c.created }})</small>
          </div>
        {% endfor %}
      </div>
    </div>
  {% endfor %}
{% endblock %}
""",
        posts=posts,
        comments=comments,
        reactions=reactions,
    )


@app.route("/register", methods=["GET", "POST"])
def register() -> str:
    """Display a registration form and handle new user registration."""
    error: Optional[str] = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "All fields are required."
        else:
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, pwd_hash),
                )
                conn.commit()
                conn.close()
                # Automatically log in after successful registration
                session["username"] = username
                return redirect(url_for("home"))
            except sqlite3.IntegrityError:
                error = "Username already exists."
                conn.close()
    return render_template_string(
        BASE_TEMPLATE
        + """
{% block content %}
  <h1>Register</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post">
    <input name="username" placeholder="Username" required><br>
    <input name="password" placeholder="Password" type="password" required><br>
    <button type="submit">Register</button>
  </form>
  <p>Already have an account? <a href="{{ url_for('login') }}">Login here</a>.</p>
{% endblock %}
""",
        error=error,
    )


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    """Display login form and authenticate a user."""
    error: Optional[str] = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        if user and user["password_hash"] == pwd_hash:
            session["username"] = username
            next_url = request.args.get("next") or url_for("home")
            return redirect(next_url)
        else:
            error = "Invalid credentials"
    return render_template_string(
        BASE_TEMPLATE
        + """
{% block content %}
  <h1>Login</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post">
    <input name="username" placeholder="Username" required><br>
    <input name="password" placeholder="Password" type="password" required><br>
    <button type="submit">Login</button>
  </form>
  <p>Don't have an account? <a href="{{ url_for('register') }}">Register here</a>.</p>
{% endblock %}
""",
        error=error,
    )


@app.route("/logout")
def logout() -> str:
    """Log the user out and redirect to the feed."""
    session.clear()
    return redirect(url_for("home"))


@app.route("/add", methods=["POST"])
@login_required
def add() -> str:
    """Handle creation of a new post."""
    body = request.form.get("body", "").strip()
    if not body:
        return redirect(url_for("home"))
    conn = get_db()
    conn.execute(
        "INSERT INTO posts (author, body, created) VALUES (?,?,?)",
        (
            g.user,
            body,
            datetime.datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    conn.commit(); conn.close()
    return redirect(url_for("home"))


@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment(post_id: int) -> str:
    """Handle adding a comment to a post."""
    body = request.form.get("body", "").strip()
    if not body:
        return redirect(url_for("home"))
    conn = get_db()
    conn.execute(
        "INSERT INTO comments (post_id, author, body, created) VALUES (?,?,?,?)",
        (
            post_id,
            g.user,
            body,
            datetime.datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    conn.commit(); conn.close()
    return redirect(url_for("home"))


@app.route("/react/<int:post_id>", methods=["POST"])
@login_required
def react(post_id: int) -> str:
    """Handle adding a reaction (emoji) to a post."""
    emoji = request.form.get("emoji")
    if not emoji:
        abort(400)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO reactions (post_id, author, emoji) VALUES (?, ?, ?)",
            (post_id, g.user, emoji),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Duplicate reaction by same user for the same emoji; silently ignore
        pass
    finally:
        conn.close()
    return redirect(url_for("home"))


if __name__ == "__main__":
    """
    When run directly (``python mini_fb.py``), ensure the database is initialised
    and start the Flask development server.  The port defaults to 5000 but
    honours the ``PORT`` environment variable if set.  The server binds to
    ``0.0.0.0`` so that it is reachable from outside the container when
    deployed to platforms like Render.
    """
    import os

    # Only enable debug mode in a local development environment.  When
    # deploying to a production platform like Render you can set
    # FLASK_DEBUG=0 to disable debug mode.
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1",
            host="0.0.0.0",
            port=port)