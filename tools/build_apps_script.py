"""Build the Google Apps Script version from the shared definitions.

    python tools/build_apps_script.py

Reads app/fields.py + app/i18n.py (so fields, validation messages and translations stay identical to the
Flask version) and writes:
    apps_script/Code.gs            CONFIG + logic.js + the page + server.js   (the ONLY file to paste into Apps Script)
    apps_script/Index.html         the employee page with logic.js embedded (reference / tests)
    apps_script/appsscript.json    manifest
    apps_script/test/config.json   CONFIG for the Node tests
    apps_script/test/vectors.json  expected validation results from the Python code (parity test)
"""
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import fields as F  # noqa: E402
from app import i18n as I  # noqa: E402

OUT = os.path.join(ROOT, "apps_script")
TODAY = date(2026, 10, 13)  # fixed "today" for the parity vectors
STATUSES = {"unopened": "لم يفتح", "draft": "قيد التعبئة", "submitted": "بانتظار المراجعة",
            "returned": "معاد للتعديل", "approved": "معتمد"}


def _flat(ar, table):
    return {"ar": ar, **table}


def config():
    fields = [{
        "key": f.key, "label": f.label, "xlsx": f.xlsx, "section": f.section, "kind": f.kind, "required": f.required,
        "options": f.options, "owner": f.owner, "repOnly": f.rep_only, "sensitive": f.sensitive,
        "vehicle": f.vehicle, "hint": f.hint, "datalist": f.datalist,
    } for f in F.FIELDS]
    hints = {}
    for f in F.FIELDS:
        table = I.HINTS.get(f.key)
        if table:
            hints[f.key] = _flat(f.hint, table)
        elif f.hint:
            hints[f.key] = {"ar": f.hint}
    return {
        "fields": fields,
        "options": F.OPTIONS,
        "datalists": F.DATALISTS,
        "sections": [list(s) for s in F.SECTIONS],
        "sectionGroup": F.SECTION_GROUP,
        "groupTitles": {k: _flat(dict(F.GROUPS)[k], t) for k, t in I.GROUP_TITLES.items()},
        "vehicleValues": list(F.VEHICLE_VALUES),
        "photoKeys": F.PHOTO_KEYS,
        "expiryKeys": [list(k) for k in F.EXPIRY_KEYS],
        "statuses": STATUSES,
        "langs": {code: [name, direction] for code, (name, direction) in I.LANGS.items()},
        "natLang": I.NAT_LANG,
        "waMessage": I.WA_MESSAGE,
        "ui": {k: _flat(ar, t) for k, (ar, t) in I.UI.items()},
        "sectionTitles": {k: _flat(dict(F.SECTIONS)[k], t) for k, t in I.SECTION_TITLES.items()},
        "fieldLabels": {k: _flat(F.BY_KEY[k].label, t) for k, t in I.FIELD_LABELS.items()},
        "hints": hints,
        "optionLabels": {k: _flat(k, t) for k, t in I.OPTION_LABELS.items()},
        "messages": {k: _flat(k, t) for k, t in I.MESSAGES.items()},
    }


def vectors():
    """(field key, raw input) -> expected (value, error) from the Python implementation."""
    common = ["", "  ", "x", "x" * 201, "  spaced   out  "]
    by_kind = {
        "date": ["2030-01-05", "2030-1-5", "2030/01/05", "05/01/2030", "5-1-2030", "2030-02-30", "1989-12-31", "2101-01-01",
                 "٢٠٣٠-٠١-٠٥", "not a date", "2030-13-01", "1930-01-01", "2012-10-14", "2012-10-13", "2026-10-13"],
        "phone": ["0512345678", "512345678", "+966512345678", "966512345678", "00966512345678", "966 51 234 5678", "05-1234-5678",
                  "0412345678", "05123", "٠٥١٢٣٤٥٦٧٨", "abc", "+9665123456789"],
        "phone_intl": ["+91 98765 43210", "0091 98765 43210", "+880 1712-345678", "03001234567", "0512345678", "966512345678",
                       "+966512345678", "123", "abc", "+1 (555) 123-4567", "+123456789012345", "+1234567890123456"],
        "id": ["1234567890", "2234567890", "3234567890", "123456789", "12345678901", "١٢٣٤٥٦٧٨٩٠", "12345 67890", "abcdefghij"],
        "iban": ["SA0380000000608010167519", "sa03 8000 0000 6080 1016 7519", "SA0380000000608010167518", "GB82WEST12345698765432",
                 "SA03", "SA038000000060801016751"],
        "email": ["A@B.COM", "a@b", "a b@c.com", "name@example.org", "@x.com"],
        "select": [],
    }
    out = []
    for f in F.FIELDS:
        if f.kind == "photo":
            continue
        inputs = list(common) + by_kind.get(f.kind, [])
        if f.kind == "select":
            inputs += list(F.OPTIONS[f.options]) + ["not-an-option", "ذكر "]
        for raw in inputs:
            value, err = F.clean(f, raw, today=TODAY)
            out.append({"key": f.key, "raw": raw, "value": value, "error": err})
    miss = []
    samples = [
        ({}, {}, False), ({"id_type": "إقامة"}, {}, False), ({"vehicle_type": "سيارة الشركة"}, {}, True),
        ({"vehicle_type": "بدون مركبة"}, {}, True), ({"vehicle_type": "سيارة شخصية", "plate_no": "x"}, {"photo_front": "u"}, True),
        ({"name_en": "A", "nationality": "هندي", "gender": "ذكر"}, {}, False),
    ]
    for data, photos, is_rep in samples:
        for owner in (None, "employee", "hr"):
            miss.append({"data": data, "photos": photos, "isRep": is_rep, "owner": owner,
                         "missing": F.missing(data, photos, is_rep, owner=owner)})
    names = [{"data": d, "fallback": fb, "name": F.display_name(d, fb)} for d, fb in
             [({}, ""), ({}, "E1"), ({"name_en": "Ravi"}, "E1"), ({"name_ar": "أحمد", "name_en": "Ahmed"}, "")]]
    return {"today": TODAY.isoformat(), "clean": out, "missing": miss, "names": names}


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def build():
    cfg = config()
    cfg_json = json.dumps(cfg, ensure_ascii=False, indent=1)
    logic = read(os.path.join(OUT, "src", "logic.js"))
    server = read(os.path.join(OUT, "src", "server.js"))
    header = ("// GENERATED by tools/build_apps_script.py. Do not edit here: edit apps_script/src/* and the Python\n"
              "// field definitions, then run:  python tools/build_apps_script.py\n\n")
    index = read(os.path.join(OUT, "src", "Index.template.html")).replace("/*__LOGIC__*/", logic)
    write(os.path.join(OUT, "Index.html"), index)   # standalone copy (tests / reference); Code.gs embeds it
    embedded = "// the employee page (same as Index.html), embedded so that Code.gs is the only file to install\n" \
               "const INDEX_HTML = " + json.dumps(index, ensure_ascii=False) + ";\n\n"
    code = header + "const CONFIG = " + cfg_json + ";\n\n" + logic + "\n" + embedded + server
    write(os.path.join(OUT, "Code.gs"), code)
    write(os.path.join(OUT, "appsscript.json"), json.dumps({
        "timeZone": "Asia/Riyadh",
        "dependencies": {},
        "exceptionLogging": "STACKDRIVER",
        "runtimeVersion": "V8",
        "webapp": {"executeAs": "USER_DEPLOYING", "access": "ANYONE_ANONYMOUS"},
    }, indent=2) + "\n")
    write(os.path.join(OUT, "test", "config.json"), cfg_json + "\n")
    write(os.path.join(OUT, "test", "vectors.json"), json.dumps(vectors(), ensure_ascii=False, indent=1) + "\n")
    return {"Code.gs": code, "Index.html": index}


if __name__ == "__main__":
    build()
    print("built apps_script/Code.gs, Index.html, appsscript.json and test data")
