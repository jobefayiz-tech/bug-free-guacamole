import csv
import io
import os
from datetime import date
from urllib.parse import quote

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
                   request, send_file, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, xlsx_io
from .fields import (BY_KEY, EXPIRY_KEYS, PHOTO_KEYS, display_name, fields_for, mask, missing,
                     parse_date)
from .i18n import LANGS, auto_language, whatsapp_text
from .forms import changed_labels, label, parse_form, photo_path, sections, store_photos
from .security import login_required

bp = Blueprint("admin", __name__)

PAGE = 50
DUMMY_HASH = generate_password_hash("x" * 12)
STATUS_FILTERS = [
    ("", "كل الحالات"), ("unopened", "لم يفتح الرابط"), ("draft", "قيد التعبئة"),
    ("submitted", "بانتظار المراجعة"), ("returned", "معاد للتعديل"), ("approved", "معتمد"),
]


def status_key(e):
    if e["status"] == "draft":
        return "draft" if e["opened_at"] else "unopened"
    return e["status"]


def status_label(e):
    return dict(STATUS_FILTERS)[status_key(e)]


def _safe_next(path):
    ok = path and path.startswith("/") and not path.startswith("//") and "\\" not in path
    return path if ok else url_for("admin.dashboard")


@bp.route("/")
def index():
    return redirect(url_for("admin.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        key = f"login:{username}:{request.remote_addr}"
        if db.throttle_locked(key):
            error = "محاولات كثيرة. حاول بعد 15 دقيقة."
        else:
            row = db.get_db().execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
            ok = check_password_hash(row["password_hash"] if row else DUMMY_HASH, password) and row is not None
            if ok:
                session.clear()
                session["uid"] = row["id"]
                session.permanent = True
                db.throttle_reset(key)
                db.audit(username, "login")
                db.get_db().commit()
                return redirect(_safe_next(request.args.get("next")))
            db.throttle_fail(key)
            db.audit(username or "-", "login_failed")
            db.get_db().commit()
            error = "اسم المستخدم أو كلمة المرور غير صحيحة"
    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ---------------------------------------------------------------- dashboard
@bp.route("/admin")
@login_required()
def dashboard():
    emps = db.all_employees()
    counts = {k: 0 for k, _ in STATUS_FILTERS if k}
    incomplete = 0
    for e in emps:
        counts[status_key(e)] += 1
        if missing(e["data"], e["photos"], e["is_rep"]):
            incomplete += 1
    expiring = len(_alerts(emps, 30))
    pending = sorted([e for e in emps if e["status"] == "submitted"], key=lambda e: e["submitted_at"] or "")[:10]
    return render_template("dashboard.html", total=len(emps), counts=counts, incomplete=incomplete,
                           reps=sum(e["is_rep"] for e in emps), expiring=expiring, pending=pending,
                           status_filters=STATUS_FILTERS)


# ---------------------------------------------------------------- employees
@bp.route("/admin/employees")
@login_required()
def employees():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    kind = request.args.get("kind", "")
    page = max(1, request.args.get("page", 1, type=int))
    rows = db.all_employees()
    if q:
        ql = q.lower()
        rows = [e for e in rows if ql in e["emp_no"].lower() or ql in e["data"].get("name_ar", "").lower()
                or ql in e["data"].get("name_en", "").lower() or ql in e["data"].get("nationality", "").lower()
                or q in e["data"].get("mobile", "") or ql in e["data"].get("rep_code", "").lower()]
    if status:
        rows = [e for e in rows if status_key(e) == status]
    if kind == "rep":
        rows = [e for e in rows if e["is_rep"]]
    elif kind == "staff":
        rows = [e for e in rows if not e["is_rep"]]
    elif kind == "incomplete":
        rows = [e for e in rows if missing(e["data"], e["photos"], e["is_rep"])]
    total = len(rows)
    rows = rows[(page - 1) * PAGE: page * PAGE]
    items = [{"e": e, "label": status_label(e), "key": status_key(e),
              "todo": len(missing(e["data"], e["photos"], e["is_rep"]))} for e in rows]
    return render_template("employees.html", items=items, q=q, status=status, kind=kind, page=page,
                           pages=max(1, -(-total // PAGE)), total=total, status_filters=STATUS_FILTERS)


@bp.route("/admin/employees/<emp_no>")
@login_required()
def employee(emp_no):
    emp = db.get_employee(emp_no) or abort(404)
    reveal = request.args.get("reveal") == "1"
    if reveal:
        db.audit(g.user["username"], "reveal_sensitive", emp_no)
        db.get_db().commit()
    rows = db.get_db().execute(
        "SELECT * FROM audit WHERE emp_no=? ORDER BY id DESC LIMIT 25", (emp_no,)).fetchall()
    todo = missing(emp["data"], emp["photos"], emp["is_rep"])
    return render_template(
        "employee_detail.html", emp=emp, sections=sections(emp["is_rep"], full=True), reveal=reveal, mask=mask,
        todo=todo, todo_labels=[BY_KEY[k].label for k in todo], history=rows, status=status_label(emp))


@bp.route("/admin/employees/<emp_no>/edit", methods=["GET", "POST"])
@login_required()
def edit(emp_no):
    emp = db.get_employee(emp_no) or abort(404)
    errors, photo_errors, raw = {}, {}, {}
    if request.method == "POST":
        editable = [f for f in fields_for(emp["is_rep"], full=True) if f.key not in ("consent", "location_consent")]
        is_rep = bool(request.form.get("is_rep"))
        fields = fields_for(is_rep, full=True) if is_rep else [f for f in editable if not f.rep_only]
        data, errors = parse_form(request.form, emp["data"], [f for f in fields if f.key not in ("consent", "location_consent")])
        photos, photo_errors, photo_changed = store_photos(emp, request.files, PHOTO_KEYS)
        raw = {k: v[1] for k, v in errors.items()}
        errors = {k: v[0] for k, v in errors.items()}
        db.update_employee(emp_no, data=data, photos=photos, is_rep=is_rep, updated_at=db.now_iso())
        changed = changed_labels(emp["data"], data) + ["صورة: " + label(k) for k in photo_changed]
        if is_rep != emp["is_rep"]:
            changed.append("نوع الموظف (مندوب)")
        db.audit(g.user["username"], "hr_edit", emp_no, "الحقول: " + "، ".join(changed) if changed else "")
        db.get_db().commit()
        if not errors and not photo_errors:
            flash("تم حفظ التعديلات", "ok")
            return redirect(url_for("admin.employee", emp_no=emp_no))
        emp = db.get_employee(emp_no)
    values = {**emp["data"], **raw}
    return render_template("employee_edit.html", emp=emp, values=values, errors=errors,
                           photo_errors=photo_errors, sections=sections(True, full=True))


@bp.route("/admin/employees/<emp_no>/review", methods=["POST"])
@login_required()
def review(emp_no):
    emp = db.get_employee(emp_no) or abort(404)
    action = request.form.get("action")
    note = request.form.get("note", "").strip()[:500]
    if action == "approve" and emp["status"] == "submitted":
        todo = missing(emp["data"], emp["photos"], emp["is_rep"])
        if todo:
            flash("لا يمكن الاعتماد: توجد حقول مطلوبة ناقصة (راجع القائمة أدناه). أكملها أو أعد السجل للموظف.", "err")
            return redirect(url_for("admin.employee", emp_no=emp_no))
        status = "approved"
    elif action == "return" and emp["status"] in ("submitted", "approved"):
        if not note:
            flash("اكتب سبب الإعادة ليراه الموظف", "err")
            return redirect(url_for("admin.employee", emp_no=emp_no))
        status = "returned"
    else:
        abort(400)
    db.update_employee(emp_no, status=status, review_note=note if status == "returned" else "",
                       reviewed_at=db.now_iso(), reviewed_by=g.user["username"])
    db.audit(g.user["username"], "approve" if status == "approved" else "return", emp_no, note)
    db.get_db().commit()
    flash("تم الاعتماد" if status == "approved" else "تمت إعادة السجل للموظف", "ok")
    return redirect(url_for("admin.employee", emp_no=emp_no))


@bp.route("/admin/employees/<emp_no>/regen-link", methods=["POST"])
@login_required()
def regen_link(emp_no):
    db.get_employee(emp_no) or abort(404)
    db.update_employee(emp_no, token=db.new_token())
    db.audit(g.user["username"], "regen_link", emp_no)
    db.get_db().commit()
    flash("تم إنشاء رابط جديد وأُلغي الرابط القديم", "ok")
    return redirect(url_for("admin.employee", emp_no=emp_no))


@bp.route("/admin/photo/<emp_no>/<key>")
@login_required()
def photo(emp_no, key):
    emp = db.get_employee(emp_no) or abort(404)
    if key not in PHOTO_KEYS or key not in emp["photos"]:
        abort(404)
    path = photo_path(emp_no, key)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="image/jpeg")


# ---------------------------------------------------------------- import / export
@bp.route("/admin/import", methods=["GET", "POST"])
@login_required()
def import_page():
    report = None
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".xlsx"):
            flash("اختر ملف Excel بصيغة xlsx", "err")
        else:
            dry = bool(request.form.get("dry_run"))
            try:
                report = xlsx_io.import_workbook(f.stream, g.user["username"], dry_run=dry)
            except Exception:
                current_app.logger.exception("import failed")
                db.get_db().rollback()
                flash("تعذّر قراءة الملف. تأكد أنه القالب الرسمي وغير تالف.", "err")
            else:
                if not dry:
                    db.audit(g.user["username"], "import", None,
                             f"جديد {report['created']} / محدّث {report['updated']} / أخطاء {len(report['errors'])}")
                    db.get_db().commit()
    return render_template("import.html", report=report)


@bp.route("/admin/template.xlsx")
@login_required()
def template_file():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return send_from_directory(root, "employee-data-template.xlsx", as_attachment=True)


@bp.route("/admin/export.xlsx")
@login_required()
def export():
    db.audit(g.user["username"], "export", None, "تصدير جميع البيانات إلى Excel")
    db.get_db().commit()
    out = xlsx_io.build_export(db.all_employees())
    return send_file(out, as_attachment=True, download_name=f"employees-{date.today().isoformat()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- links
def _wa_number(mobile):
    return "966" + mobile[1:] if mobile.startswith("05") else ""


def _link_rows(request_obj, only, lang="auto", q=""):
    base = current_app.config.get("BASE_URL") or request_obj.host_url.rstrip("/")
    rows = []
    for e in db.all_employees():
        if only == "pending" and e["status"] in ("submitted", "approved"):
            continue
        if only == "unopened" and e["opened_at"]:
            continue
        d = e["data"]
        if q and q.lower() not in " ".join([e["emp_no"], d.get("name_ar", ""), d.get("name_en", ""),
                                            d.get("nationality", "")]).lower():
            continue
        use = auto_language(d) if lang == "auto" else lang
        link = f"{base}/e/{e['token']}" + (f"?lang={use}" if use != "ar" else "")
        name = display_name(d)
        num = _wa_number(d.get("mobile", ""))
        msg = whatsapp_text(use, name, link)
        rows.append({"e": e, "link": link, "name": name, "mobile": d.get("mobile", ""), "lang": use,
                     "nat": d.get("nationality", ""),
                     "wa": f"https://wa.me/{num}?text={quote(msg)}" if num else ""})
    return rows


def _link_args():
    lang = request.args.get("lang", "auto")
    return (request.args.get("only", "pending"), lang if lang in LANGS else "auto", request.args.get("q", "").strip())


@bp.route("/admin/links")
@login_required()
def links():
    only, lang, q = _link_args()
    rows = _link_rows(request, only, lang, q)
    return render_template("links.html", rows=rows[:300], total=len(rows), only=only, lang=lang, q=q, langs=LANGS)


@bp.route("/admin/links.csv")
@login_required()
def links_csv():
    only, lang, q = _link_args()
    db.audit(g.user["username"], "export_links", None, only)
    db.get_db().commit()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["الرقم الوظيفي", "الاسم", "الجنسية", "الجوال", "لغة الرابط", "الرابط", "رابط واتساب"])
    for r in _link_rows(request, only, lang, q):
        w.writerow([r["e"]["emp_no"], r["name"], r["nat"], r["mobile"], r["lang"], r["link"], r["wa"]])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=links.csv"})


# ---------------------------------------------------------------- alerts
def _alerts(emps, days):
    today = date.today()
    out = []
    for e in emps:
        if e["data"].get("employment_status") == "منتهية خدمته":
            continue
        for key, title in EXPIRY_KEYS:
            if key in ("license_expiry", "registration_expiry") and not e["is_rep"]:
                continue
            d = parse_date(e["data"].get(key, ""))
            if d is None:
                continue
            left = (d - today).days
            if left <= days:
                out.append({"e": e, "doc": title, "date": d.isoformat(), "left": left})
    return sorted(out, key=lambda a: a["left"])


@bp.route("/admin/alerts")
@login_required()
def alerts():
    days = request.args.get("days", 60, type=int)
    days = days if days in (30, 60, 90) else 60
    return render_template("alerts.html", rows=_alerts(db.all_employees(), days), days=days)


# ---------------------------------------------------------------- audit / users
@bp.route("/admin/audit")
@login_required()
def audit_log():
    page = max(1, request.args.get("page", 1, type=int))
    emp_no = request.args.get("emp_no", "").strip()
    where, args = ("WHERE emp_no=?", [emp_no]) if emp_no else ("", [])
    rows = db.get_db().execute(
        f"SELECT * FROM audit {where} ORDER BY id DESC LIMIT 100 OFFSET ?", args + [(page - 1) * 100]).fetchall()
    return render_template("audit.html", rows=rows, page=page, emp_no=emp_no)


@bp.route("/admin/users", methods=["GET", "POST"])
@login_required(admin_only=True)
def users():
    conn = db.get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role") if request.form.get("role") in ("admin", "hr") else "hr"
            if not username.isascii() or not username.replace("_", "").replace(".", "").isalnum():
                flash("اسم المستخدم: أحرف إنجليزية وأرقام فقط", "err")
            elif len(password) < 10:
                flash("كلمة المرور يجب ألا تقل عن 10 خانات", "err")
            elif conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                flash("اسم المستخدم مستخدم من قبل", "err")
            else:
                conn.execute("INSERT INTO users(username, password_hash, role, created_at) VALUES (?,?,?,?)",
                             (username, generate_password_hash(password), role, db.now_iso()))
                db.audit(g.user["username"], "user_create", None, f"{username} ({role})")
                conn.commit()
                flash("تم إنشاء المستخدم", "ok")
        elif action == "toggle":
            uid = request.form.get("uid", type=int)
            if uid == g.user["id"]:
                flash("لا يمكنك تعطيل حسابك", "err")
            else:
                conn.execute("UPDATE users SET active = 1 - active WHERE id=?", (uid,))
                db.audit(g.user["username"], "user_toggle", None, str(uid))
                conn.commit()
        elif action == "password":
            uid = request.form.get("uid", type=int)
            password = request.form.get("password", "")
            if len(password) < 10:
                flash("كلمة المرور يجب ألا تقل عن 10 خانات", "err")
            else:
                conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), uid))
                db.audit(g.user["username"], "user_password", None, str(uid))
                conn.commit()
                flash("تم تغيير كلمة المرور", "ok")
        return redirect(url_for("admin.users"))
    return render_template("users.html", rows=conn.execute("SELECT * FROM users ORDER BY id").fetchall())


@bp.route("/admin/password", methods=["GET", "POST"])
@login_required()
def my_password():
    if request.method == "POST":
        old, new = request.form.get("old", ""), request.form.get("new", "")
        if not check_password_hash(g.user["password_hash"], old):
            flash("كلمة المرور الحالية غير صحيحة", "err")
        elif len(new) < 10:
            flash("كلمة المرور الجديدة يجب ألا تقل عن 10 خانات", "err")
        else:
            db.get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), g.user["id"]))
            db.audit(g.user["username"], "password_change")
            db.get_db().commit()
            flash("تم تغيير كلمة المرور", "ok")
            return redirect(url_for("admin.dashboard"))
    return render_template("password.html")
