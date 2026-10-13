import os
import re

from openpyxl import load_workbook

from app.fields import (BY_KEY, EMP_NO_XLSX, FIELDS, OPTIONS, clean, iban_ok, mask, missing, normalize)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_arabic_digits_normalized():
    assert normalize("٠٥١٢٣٤٥٦٧٨") == "0512345678"
    assert clean(BY_KEY["mobile"], "٠٥١٢٣٤٥٦٧٨") == ("0512345678", None)


def test_mobile_formats():
    f = BY_KEY["mobile"]
    for raw in ("0512345678", "512345678", "+966512345678", "966 51 234 5678", "00966512345678"):
        assert clean(f, raw) == ("0512345678", None), raw
    for raw in ("0412345678", "05123", "abc"):
        assert clean(f, raw)[1], raw


def test_id_number_rules():
    f = BY_KEY["id_number"]
    assert clean(f, "1234567890")[1] is None
    assert clean(f, "2234567890")[1] is None
    assert clean(f, "3234567890")[1]
    assert clean(f, "123456789")[1]


def test_iban():
    assert iban_ok("SA0380000000608010167519")          # standard published example
    assert not iban_ok("SA0380000000608010167518")      # checksum broken
    assert not iban_ok("GB82WEST12345698765432")
    assert clean(BY_KEY["iban"], "sa03 8000 0000 6080 1016 7519") == ("SA0380000000608010167519", None)


def test_dates():
    f = BY_KEY["id_expiry"]
    assert clean(f, "2030-1-5") == ("2030-01-05", None)  # non zero-padded input is accepted and normalized
    assert clean(f, "15/03/2030") == ("2030-03-15", None)
    assert clean(f, "2030-03-15") == ("2030-03-15", None)
    assert clean(f, "not a date")[1]
    assert clean(BY_KEY["birth_date"], "2024-01-01")[1]  # too young


def test_select_rejects_unknown():
    assert clean(BY_KEY["gender"], "ذكر")[1] is None
    assert clean(BY_KEY["gender"], "x")[1]


def test_mask():
    assert mask(BY_KEY["id_number"], "1234567890") == "••••••7890"
    assert mask(BY_KEY["name_ar"], "أحمد") == "أحمد"
    assert mask(BY_KEY["birth_date"], "1990-05-01").startswith("1990")


def test_missing_vehicle_rules():
    base = {"vehicle_type": "بدون مركبة"}
    keys = missing(base, {}, True, owner="employee")
    assert "plate_no" not in keys and "photo_front" not in keys
    keys = missing({"vehicle_type": "سيارة الشركة"}, {}, True, owner="employee")
    for k in ("plate_no", "license_no", "license_expiry", "registration_expiry", "photo_front", "photo_odometer"):
        assert k in keys
    assert "app_id" not in missing({}, {}, False)  # rep-only fields never required for staff


def test_template_matches_fields():
    """tools/make_template.py and app/fields.py must describe the same columns and lists."""
    ns = {"__file__": os.path.join(ROOT, "tools", "make_template.py")}
    src = open(os.path.join(ROOT, "tools", "make_template.py"), encoding="utf-8").read()
    src = src.split("wb = Workbook()")[0]  # definitions only
    exec(compile(src, "make_template", "exec"), ns)
    tpl_emp = [c[0] for c in ns["EMP_COLS"]]
    tpl_rep = [c[0] for c in ns["REP_COLS"]]
    app_emp = [EMP_NO_XLSX] + [f.xlsx for f in FIELDS if not f.rep_only]
    app_rep = [EMP_NO_XLSX] + [f.xlsx for f in FIELDS if f.rep_only]
    assert sorted(tpl_emp) == sorted(app_emp)
    assert sorted(tpl_rep) == sorted(app_rep)
    tpl_lists = {tuple(v) for v in ns["LISTS"].values()}
    app_lists = {tuple(v) for v in OPTIONS.values()}
    assert tpl_lists == app_lists
    # required flags agree
    tpl_req = {c[0]: c[1] for c in ns["EMP_COLS"] + ns["REP_COLS"]}
    for f in FIELDS:
        if f.vehicle or f.key == "iqama_profession":
            continue
        assert tpl_req[f.xlsx] == f.required, f.key


def test_shipped_template_has_all_headers():
    wb = load_workbook(os.path.join(ROOT, "employee-data-template.xlsx"))
    heads = {re.sub(r"\s*\*$", "", c.value) for c in wb["الموظفون"][1]} | {re.sub(r"\s*\*$", "", c.value) for c in wb["المناديب"][1]}
    for f in FIELDS:
        assert f.xlsx in heads, f.xlsx
