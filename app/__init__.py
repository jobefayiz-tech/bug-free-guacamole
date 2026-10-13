import os
import secrets
from datetime import timedelta

from flask import Flask, g, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db, security
from .fields import DATALISTS, OPTIONS, VEHICLE_VALUES, display_name, is_required, mask


def create_app(test_config=None):
    app = Flask(__name__)
    data_dir = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")))
    app.config.update(
        DATA_DIR=data_dir,
        DB_PATH=os.path.join(data_dir, "app.db"),
        UPLOAD_DIR=os.path.join(data_dir, "uploads"),
        BASE_URL=os.environ.get("BASE_URL", "").rstrip("/"),
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("HTTPS", "") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    if test_config:
        app.config.update(test_config)
        data_dir = app.config["DATA_DIR"]
        app.config.setdefault("DB_PATH", os.path.join(data_dir, "app.db"))
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    app.secret_key = os.environ.get("SECRET_KEY") or _secret_key(data_dir)
    if os.environ.get("TRUST_PROXY") == "1":  # running behind Caddy/Nginx
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_db(app)
    app.teardown_appcontext(db.close_db)
    app.before_request(security.load_user)
    app.before_request(security.check_csrf)
    app.after_request(security.add_headers)

    from . import views_admin, views_employee
    app.register_blueprint(views_admin.bp)
    app.register_blueprint(views_employee.bp)

    app.jinja_env.globals.update(csrf_token=security.csrf_token, OPTIONS=OPTIONS,
                                VEHICLE_VALUES=list(VEHICLE_VALUES), is_required=is_required,
                                DATALISTS=DATALISTS, dname=display_name)
    app.jinja_env.filters["local"] = db.to_local
    app.jinja_env.filters["mask"] = lambda v, f: mask(f, v)

    @app.context_processor
    def inject():
        return {"user": getattr(g, "user", None)}

    for code, msg in ((400, "طلب غير صالح. أعد تحميل الصفحة وحاول مرة أخرى."), (403, "ليست لديك صلاحية لهذه الصفحة."),
                      (404, "الصفحة أو الرابط غير موجود. تأكد من الرابط أو اطلب رابطًا جديدًا من الموارد البشرية."),
                      (413, "حجم الملفات المرفوعة كبير جدًا."), (500, "حدث خطأ غير متوقع. حاول لاحقًا.")):
        app.register_error_handler(code, lambda e, code=code, msg=msg: (render_template("error.html", code=code, msg=msg), code))
    return app


def _secret_key(data_dir):
    path = os.path.join(data_dir, "secret_key")
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()
