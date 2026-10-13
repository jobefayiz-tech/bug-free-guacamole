import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_apps_script as build  # noqa: E402

AS = os.path.join(ROOT, "apps_script")
NODE = shutil.which("node")


def read(*parts):
    with open(os.path.join(AS, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_generated_files_are_up_to_date():
    """Code.gs / Index.html / test data must be regenerated (python tools/build_apps_script.py) after any change."""
    built = build.build()
    assert read("Code.gs") == built["Code.gs"]
    assert read("Index.html") == built["Index.html"]
    assert json.loads(read("test", "config.json")) == build.config()
    assert json.loads(read("test", "vectors.json")) == build.vectors()


def test_index_html_has_exactly_one_server_scriptlet():
    """Apps Script treats '<?' in an HTML file as a scriptlet: our page must contain only the boot one."""
    html = read("Index.html")
    assert html.count("<?") == 1 and html.count("?>") == 1 and "<?!= boot ?>" in html


def test_manifest_allows_anonymous_web_app_run_as_owner():
    m = json.loads(read("appsscript.json"))
    assert m["runtimeVersion"] == "V8" and m["timeZone"] == "Asia/Riyadh"
    assert m["webapp"] == {"executeAs": "USER_DEPLOYING", "access": "ANYONE_ANONYMOUS"}


def test_every_public_function_is_intentional():
    """Anything not ending in '_' can be called from the web page: keep that list tiny and reviewed."""
    code = read("Code.gs")
    public = sorted(set(re.findall(r"^function ([A-Za-z0-9]+)\(", code, re.M)))
    allowed = {"doGet", "onOpen", "onEdit",
               "apiStart", "apiVerify", "apiLoad", "apiSave", "apiPhoto",                       # employee page
               "setupSheets", "prepareLinks", "setBaseUrl", "recomputeAll", "buildAlerts",      # HR menu (guarded by getUi)
               "regenLinkForRow", "backupNow"}
    assert set(public) == allowed, set(public) ^ allowed
    # every HR-menu function must start by calling adminUi_() (throws outside the Sheet UI)
    for name in ("setupSheets", "prepareLinks", "setBaseUrl", "recomputeAll", "buildAlerts", "regenLinkForRow", "backupNow"):
        body = re.search(r"function %s\(\) \{\n(.*?)\n" % name, code).group(1)
        assert "adminUi_()" in body, name


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_node_suite_passes():
    r = subprocess.run([NODE, "--test", os.path.join(AS, "test", "gas.test.js")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_page_scripts_are_valid_javascript(tmp_path):
    html = read("Index.html")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 3
    for i, js in enumerate(scripts):
        js = js.replace("<?!= boot ?>", "{}")
        f = tmp_path / f"s{i}.js"
        f.write_text(js, encoding="utf-8")
        r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    code = tmp_path / "code.js"
    code.write_text(read("Code.gs"), encoding="utf-8")
    assert subprocess.run([NODE, "--check", str(code)], capture_output=True, text=True).returncode == 0
