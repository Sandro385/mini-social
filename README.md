Mini FB – a minimal social network
=================================

This project implements a tiny social networking application using
`Flask` and `SQLite`.  It allows users to register accounts,
log in, create posts, comment on posts, and react with emojis.
The interface is intentionally simple and uses inlined HTML templates
so that everything lives in a single Python file.

Features
--------

* **User registration & login** – credentials are stored as SHA‑256
  hashes in a local SQLite database.  Once authenticated, the user
  session is tracked via cookies.
* **Post feed** – authenticated users can write short posts which
  appear on the home page ordered by creation time (most recent
  first).
* **Comments** – any logged‑in user can add comments on a post.  The
  comments are displayed beneath the corresponding post.
* **Emoji reactions** – users can react to posts with one of two
  emojis (👍 or ❤️).  Each user can only react with a given emoji
  once on a post.  A count of reactions for each emoji is shown.
* **Anonymous browsing** – visitors who are not logged in can browse
  the feed but must register or log in to participate.

Getting started locally
-----------------------

1. **Install Python 3.11+** and create a virtual environment (optional
   but recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies** from the provided requirements file:

   ```bash
   pip install -r mini_fb_requirements.txt
   ```

3. **Run the application**:

   ```bash
   python mini_fb.py
   ```

   The server will start on <http://localhost:5000>.  You can log in
   or register from the links shown on the home page.

Deployment notes
----------------

The application is designed to be container‑friendly.  A sample
`Dockerfile` is included which installs dependencies, copies the
application and starts it with Python.  When deployed to a platform
like Render or Cloud Run:

* The server binds to `0.0.0.0` and reads the `PORT` environment
  variable if set (default is 5000).  Render will supply its own port.
* The SQLite database file (`mini_fb.db`) resides next to the
  application code.  On platforms without persistent storage you will
  lose data when the container restarts.  To persist data across
  restarts, mount a persistent disk and set `DB_PATH` accordingly.
* Set a strong `SECRET_KEY` in the environment to secure user
  sessions: e.g. `FLASK_SECRET_KEY=<random string>`.  The default
  included in the code is for development only.

License
-------

This project is provided without any warranty.  Feel free to use it
as a starting point for your own applications.