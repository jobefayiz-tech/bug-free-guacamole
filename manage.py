"""Command-line helpers.

    python manage.py createuser <username> [--admin]
    python manage.py passwd <username>
"""
import getpass
import sys

from werkzeug.security import generate_password_hash

from app import create_app, db


def _ask_password():
    pw = getpass.getpass("كلمة المرور (10 خانات فأكثر / password, 10+ chars): ")
    if len(pw) < 10:
        sys.exit("كلمة المرور قصيرة / password too short")
    if pw != getpass.getpass("أعدها للتأكيد / repeat: "):
        sys.exit("غير متطابقتين / passwords do not match")
    return pw


def main(argv):
    if len(argv) < 3 or argv[1] not in ("createuser", "passwd"):
        sys.exit(__doc__)
    app = create_app()
    username = argv[2].strip().lower()
    with app.app_context():
        conn = db.get_db()
        if argv[1] == "createuser":
            role = "admin" if "--admin" in argv else "hr"
            if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                sys.exit("المستخدم موجود / user exists")
            conn.execute("INSERT INTO users(username, password_hash, role, created_at) VALUES (?,?,?,?)",
                         (username, generate_password_hash(_ask_password()), role, db.now_iso()))
            conn.commit()
            print(f"تم إنشاء المستخدم {username} ({role})")
        else:
            if not conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                sys.exit("المستخدم غير موجود / no such user")
            conn.execute("UPDATE users SET password_hash=? WHERE username=?",
                         (generate_password_hash(_ask_password()), username))
            conn.commit()
            print("تم تغيير كلمة المرور")


if __name__ == "__main__":
    main(sys.argv)
