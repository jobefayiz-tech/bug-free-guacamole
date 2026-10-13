"""Consistent backup of the database and uploaded photos into one zip file.

    python tools/backup.py [output_dir]

Safe to run while the app is running. Keep the zip somewhere safe: it contains personal data.
"""
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(ROOT, "data")))


def main(out_dir="."):
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    target = os.path.join(out_dir, f"backup-{stamp}.zip")
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "app.db")
        src = sqlite3.connect(os.path.join(DATA, "app.db"))
        dst = sqlite3.connect(snap)
        src.backup(dst)  # consistent copy even while the app is writing
        dst.close()
        src.close()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "app.db")
            for folder, _, files in os.walk(os.path.join(DATA, "uploads")):
                for f in files:
                    full = os.path.join(folder, f)
                    z.write(full, os.path.join("uploads", os.path.relpath(full, os.path.join(DATA, "uploads"))))
            key = os.path.join(DATA, "secret_key")
            if os.path.exists(key):
                z.write(key, "secret_key")
    print("Backup written:", target)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
