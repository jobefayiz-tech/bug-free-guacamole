"""Form parsing and photo storage shared by the employee portal and the HR edit page."""
import os

from flask import current_app

from . import db
from .fields import CONSENT_KEYS, FIELDS, SECTIONS, clean, fields_for
from .images import process_upload


def sections(is_rep, owner=None):
    """[(section_key, title, [Field...])] for the fields that apply, optionally one owner only."""
    out = []
    for key, title in SECTIONS:
        fs = [f for f in fields_for(is_rep) if f.section == key and (owner is None or f.owner == owner)]
        if fs:
            out.append((key, title, fs))
    return out


def parse_form(form, current, fields):
    """Apply posted values to a copy of `current` data.

    Returns (new_data, errors). Invalid values are NOT stored; the raw input is returned in
    `raw` via errors[key] = (message, raw_value) so the page can re-show what was typed.
    """
    data = dict(current)
    errors = {}
    for f in fields:
        if f.kind == "photo":
            continue
        if f.key == "consent":
            data["consent"] = "نعم" if form.get("consent") else ""
            continue
        if f.key not in form:
            continue
        value, err = clean(f, form.get(f.key))
        if err:
            errors[f.key] = (err, form.get(f.key, ""))
        else:
            data[f.key] = value
    return data, errors


def photo_dir(emp_no):
    return os.path.join(current_app.config["UPLOAD_DIR"], emp_no)


def photo_path(emp_no, key):
    return os.path.join(photo_dir(emp_no), key + ".jpg")


def store_photos(emp, files, keys):
    """Save any uploaded photos. Returns (photos_dict, errors{key: msg}, changed_keys)."""
    photos = dict(emp["photos"])
    errors, changed = {}, []
    for key in keys:
        fs = files.get(key)
        if fs is None or not fs.filename:
            continue
        try:
            blob = process_upload(fs)
        except ValueError as e:
            errors[key] = str(e)
            continue
        os.makedirs(photo_dir(emp["emp_no"]), exist_ok=True)
        with open(photo_path(emp["emp_no"], key), "wb") as out:
            out.write(blob)
        photos[key] = db.now_iso()
        changed.append(key)
    return photos, errors, changed


def label(key):
    for f in FIELDS:
        if f.key == key:
            return f.label
    return key


def changed_labels(old, new):
    keys = [k for k in new if old.get(k, "") != new.get(k, "") and k not in CONSENT_KEYS]
    return [label(k) for k in keys]
