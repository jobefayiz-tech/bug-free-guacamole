import io
import os
import sys

import pytest
from openpyxl import Workbook
from PIL import Image
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db  # noqa: E402
from app.fields import EMP_NO_XLSX, BY_KEY  # noqa: E402

CSRF = "test-csrf-token"


@pytest.fixture()
def app(tmp_path):
    return create_app({"DATA_DIR": str(tmp_path), "DB_PATH": str(tmp_path / "t.db"),
                       "UPLOAD_DIR": str(tmp_path / "uploads"), "TESTING": True})


@pytest.fixture()
def client(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = CSRF
    return c


@pytest.fixture()
def admin(app, client):
    with app.app_context():
        conn = db.get_db()
        conn.execute("INSERT INTO users(username, password_hash, role, created_at) VALUES (?,?,?,?)",
                     ("boss", generate_password_hash("correct-horse-battery"), "admin", db.now_iso()))
        conn.commit()
    r = client.post("/login", data={"username": "boss", "password": "correct-horse-battery", "csrf": CSRF})
    assert r.status_code == 302
    with client.session_transaction() as s:  # login clears the session (fresh CSRF token in real use)
        s["csrf"] = CSRF
    return client


def post(client, url, data=None, **kw):
    data = dict(data or {})
    data["csrf"] = CSRF
    return client.post(url, data=data, **kw)


def png_bytes(size=(3000, 2000)):
    img = Image.new("RGB", size, (200, 30, 30))
    out = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # make
    img.save(out, "JPEG", exif=exif)
    return out.getvalue()


def make_xlsx(emp_rows, rep_rows=(), emp_headers=None, rep_headers=None):
    """rows are dicts keyed by field key (or 'emp_no')."""
    def header(k):
        return EMP_NO_XLSX if k == "emp_no" else BY_KEY[k].xlsx
    wb = Workbook()
    ws = wb.active
    ws.title = "الموظفون"
    keys = emp_headers or sorted({k for r in emp_rows for k in r}, key=lambda k: (k != "emp_no", k))
    ws.append([header(k) for k in keys])
    for r in emp_rows:
        ws.append([r.get(k) for k in keys])
    rs = wb.create_sheet("المناديب")
    keys2 = rep_headers or sorted({k for r in rep_rows for k in r}, key=lambda k: (k != "emp_no", k))
    rs.append([header(k) for k in keys2] or ["x"])
    for r in rep_rows:
        rs.append([r.get(k) for k in keys2])
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def complete_employee(emp_no="E100", **over):
    row = dict(emp_no=emp_no, name_ar="أحمد محمد", name_en="Ahmed", nationality="سعودي", gender="ذكر",
               birth_date="1990-05-01", id_type="هوية وطنية", id_number="1234567890", id_expiry="2030-01-01",
               mobile="0512345678", city="الرياض", emergency_name="خالد", emergency_relation="أخ/أخت",
               emergency_phone="0555555555", job_title="محاسب", department="المالية", work_location="الرياض",
               manager_emp_no="E1", start_date="2020-01-01", employment_status="على رأس العمل")
    row.update(over)
    return row
