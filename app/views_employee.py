import os

from flask import Blueprint, abort, g, render_template, redirect, request, send_file, session, url_for

from . import db
from .fields import PHOTO_KEYS, fields_for, has_vehicle, missing, normalize
from .forms import changed_labels, label, parse_form, photo_path, sections, store_photos
from .i18n import LANGS, Tr

bp = Blueprint("emp", __name__, url_prefix="/e")


@bp.before_request
def _language():
    lang = request.args.get("lang")
    if lang in LANGS:
        session["lang"] = lang
    g.tr = Tr(session.get("lang", "ar"))


@bp.context_processor
def _inject_language():
    return {"tr": g.tr, "langs": LANGS, "lang": g.tr.lang}


def _load(token):
    emp = db.get_employee_by_token(token)
    if emp is None:
        abort(404)
    return emp


def _verified(emp):
    return emp["emp_no"] in session.get("emp_ok", [])


def _mark_verified(emp):
    ok = session.get("emp_ok", [])
    if emp["emp_no"] not in ok:
        ok = (ok + [emp["emp_no"]])[-5:]
    session["emp_ok"] = ok


@bp.route("/<token>", methods=["GET", "POST"])
def start(token):
    emp = _load(token)
    id_number = emp["data"].get("id_number", "")
    key = "emp:" + emp["emp_no"]
    failed = False
    if _verified(emp):
        return redirect(url_for("emp.form", token=token))
    if not id_number:
        # nothing on file to check against: the secret link itself is the credential
        _mark_verified(emp)
        return redirect(url_for("emp.form", token=token))
    if db.throttle_locked(key):
        return render_template("emp_verify.html", emp=emp, failed=False, locked=True)
    if request.method == "POST":
        typed = normalize(request.form.get("last4", ""))
        mobile = emp["data"].get("mobile", "")
        # the ID on file may be wrong (that is why the data is being collected), so the mobile the link was sent to works too
        if len(typed) == 4 and typed in (id_number[-4:], mobile[-4:] if mobile else ""):
            db.throttle_reset(key)
            _mark_verified(emp)
            db.get_db().commit()
            return redirect(url_for("emp.form", token=token))
        db.throttle_fail(key)
        db.audit("emp:" + emp["emp_no"], "verify_failed", emp["emp_no"])
        db.get_db().commit()
        failed = True
    return render_template("emp_verify.html", emp=emp, failed=failed, locked=False)


@bp.route("/<token>/form", methods=["GET", "POST"])
def form(token):
    emp = _load(token)
    if not _verified(emp):
        return redirect(url_for("emp.start", token=token))
    actor = "emp:" + emp["emp_no"]
    if not emp["opened_at"]:
        db.update_employee(emp["emp_no"], opened_at=db.now_iso())
        db.audit(actor, "opened", emp["emp_no"])
        db.get_db().commit()
        emp = db.get_employee(emp["emp_no"])

    editable = [f for f in fields_for(emp["is_rep"]) if f.owner == "employee"]
    errors, raw, photo_errors, saved = {}, {}, {}, False

    if request.method == "POST":
        action = request.form.get("action", "draft")
        if emp["status"] in ("submitted", "approved"):
            action = "submit"  # changes after review always go back to HR
        data, errors = parse_form(request.form, emp["data"], editable)
        photos, photo_errors, photo_changed = store_photos(emp, request.files, [f.key for f in editable if f.kind == "photo"])
        raw = {k: v[1] for k, v in errors.items()}
        errors = {k: v[0] for k, v in errors.items()}

        cols = {"data": data, "photos": photos, "updated_at": db.now_iso()}
        if data.get("consent") == "نعم" and not emp["consent_at"]:
            cols["consent_at"] = db.now_iso()
        problems = list(errors) + list(photo_errors)
        if action == "submit":
            for k in missing(data, photos, emp["is_rep"], owner="employee"):
                errors.setdefault(k, "هذا الحقل مطلوب")
                problems.append(k)
            if not problems:
                cols.update(status="submitted", submitted_at=db.now_iso(), review_note="")
            elif emp["status"] in ("submitted", "approved"):
                cols["status"] = "draft"  # edited but not valid yet: no longer final
        db.update_employee(emp["emp_no"], **cols)
        changed = changed_labels(emp["data"], data) + ["صورة: " + label(k) for k in photo_changed]
        db.audit(actor, "employee_submit" if action == "submit" and not problems else "employee_save",
                 emp["emp_no"], "الحقول: " + "، ".join(changed) if changed else "")
        db.get_db().commit()
        if action == "submit" and not problems:
            return redirect(url_for("emp.done", token=token))
        saved = not problems
        emp = db.get_employee(emp["emp_no"])

    data = dict(emp["data"])
    data.update(raw)  # show what the user typed in fields that failed validation
    todo = missing(emp["data"], emp["photos"], emp["is_rep"], owner="employee")
    return render_template(
        "emp_form.html", emp=emp, token=token, values=data, errors=errors, photo_errors=photo_errors,
        sections=sections(emp["is_rep"]), saved=saved, todo=todo,
        locked_review=emp["status"] in ("submitted", "approved"), vehicle=has_vehicle(data),
    )


@bp.route("/<token>/done")
def done(token):
    emp = _load(token)
    if not _verified(emp):
        return redirect(url_for("emp.start", token=token))
    return render_template("emp_done.html", emp=emp)


@bp.route("/<token>/photo/<key>")
def photo(token, key):
    emp = _load(token)
    if not _verified(emp) or key not in PHOTO_KEYS or key not in emp["photos"]:
        abort(404)
    path = photo_path(emp["emp_no"], key)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="image/jpeg")
