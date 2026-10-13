import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'hr',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employees(
    emp_no TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    is_rep INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}',
    photos TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    review_note TEXT NOT NULL DEFAULT '',
    consent_at TEXT,
    opened_at TEXT,
    submitted_at TEXT,
    updated_at TEXT,
    reviewed_at TEXT,
    reviewed_by TEXT,
    fail_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit(
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    emp_no TEXT,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS audit_emp ON audit(emp_no);
CREATE TABLE IF NOT EXISTS throttle(
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT
);
"""

RIYADH = timezone(timedelta(hours=3))


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_local(ts):
    """UTC ISO string -> 'YYYY-MM-DD HH:MM' in Riyadh time."""
    if not ts:
        return ""
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(RIYADH).strftime("%Y-%m-%d %H:%M")


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(app):
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def audit(actor, action, emp_no=None, detail=""):
    get_db().execute(
        "INSERT INTO audit(ts, actor, action, emp_no, detail) VALUES (?,?,?,?,?)",
        (now_iso(), actor, action, emp_no, detail),
    )


# ------------------------------------------------------------- employees
def _row(r):
    if r is None:
        return None
    d = dict(r)
    d["data"] = json.loads(d["data"])
    d["photos"] = json.loads(d["photos"])
    d["is_rep"] = bool(d["is_rep"])
    return d


def get_employee(emp_no):
    return _row(get_db().execute("SELECT * FROM employees WHERE emp_no=?", (emp_no,)).fetchone())


def get_employee_by_token(token):
    return _row(get_db().execute("SELECT * FROM employees WHERE token=?", (token,)).fetchone())


def all_employees():
    return [_row(r) for r in get_db().execute("SELECT * FROM employees ORDER BY emp_no")]


def new_token():
    return secrets.token_urlsafe(24)


def create_employee(emp_no, data, is_rep=False):
    now = now_iso()
    get_db().execute(
        "INSERT INTO employees(emp_no, token, is_rep, data, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (emp_no, new_token(), int(is_rep), json.dumps(data, ensure_ascii=False), now, now),
    )


def update_employee(emp_no, **cols):
    """cols may contain data/photos (dicts, stored as JSON) and plain columns."""
    for k in ("data", "photos"):
        if k in cols:
            cols[k] = json.dumps(cols[k], ensure_ascii=False)
    if "is_rep" in cols:
        cols["is_rep"] = int(cols["is_rep"])
    names = list(cols)
    sql = "UPDATE employees SET " + ", ".join(f"{n}=?" for n in names) + " WHERE emp_no=?"
    get_db().execute(sql, [cols[n] for n in names] + [emp_no])


# ------------------------------------------------------------- throttle
def throttle_locked(key):
    row = get_db().execute("SELECT locked_until FROM throttle WHERE key=?", (key,)).fetchone()
    return bool(row and row["locked_until"] and row["locked_until"] > now_iso())


def throttle_fail(key, limit=5, minutes=15):
    db = get_db()
    row = db.execute("SELECT count FROM throttle WHERE key=?", (key,)).fetchone()
    count = (row["count"] if row else 0) + 1
    locked = None
    if count >= limit:
        locked = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        count = 0
    db.execute(
        "INSERT INTO throttle(key, count, locked_until) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET count=excluded.count, locked_until=excluded.locked_until",
        (key, count, locked),
    )


def throttle_reset(key):
    get_db().execute("DELETE FROM throttle WHERE key=?", (key,))
