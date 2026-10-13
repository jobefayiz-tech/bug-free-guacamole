import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from . import db


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400)


def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        row = db.get_db().execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
        g.user = row


def login_required(admin_only=False):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if g.user is None:
                return redirect(url_for("admin.login", next=request.path))
            if admin_only and g.user["role"] != "admin":
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def add_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    # employee links contain a secret token: never leak it through Referer
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    return resp
