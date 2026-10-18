"""Browser test of the employee page (Index.html) against Code.gs running on mocks.

    pip install playwright pillow      (and an installed Chromium)
    python apps_script/test/e2e_browser.py [screenshot_dir]

Starts serve.js, drives a Bengali-speaking rep through the whole flow on a phone-sized screen
and checks what ended up in the (mock) sheet and Drive.
"""
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
PORT = 8765
CHROMIUM = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")


def photo(path, size=(3000, 2000), color=(30, 90, 160)):
    img = Image.new("RGB", size, color)
    for x in range(0, size[0], 200):          # some detail so it is not a flat colour
        for y in range(0, size[1], 200):
            img.paste((x % 255, y % 255, 120), (x, y, x + 100, y + 100))
    img.save(path, "JPEG", quality=92)
    return path


def state():
    import urllib.request
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/__state"))


def main():
    server = subprocess.Popen(["node", os.path.join(HERE, "serve.js"), str(PORT)], stdout=subprocess.PIPE, text=True)
    info = json.loads(server.stdout.readline())
    base, rep, staff = info["base"], info["rep"], info["staff"]
    problems = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
            ctx = b.new_context(viewport={"width": 390, "height": 900}, is_mobile=True, has_touch=True)
            page = ctx.new_page()
            page.on("pageerror", lambda e: problems.append("pageerror: " + str(e)))
            page.on("console", lambda m: problems.append("console: " + m.text)
                    if m.type == "error" and "Failed to load resource" not in m.text else None)
            page.on("response", lambda r: problems.append(f"HTTP {r.status} {r.url}")
                    if r.status >= 400 and not r.url.endswith("favicon.ico") else None)

            # ---- bad link
            page.goto(f"{base}?t=" + "z" * 64)
            page.wait_for_selector(".flash.err")
            assert "الرابط غير صحيح" in page.inner_text("#app"), "bad link message"

            # ---- Bengali rep: verify
            page.goto(f"{base}?t={rep}&lang=bn")
            page.wait_for_selector("#last4")
            assert page.eval_on_selector("html", "e => [e.lang, e.dir]") == ["bn", "ltr"]
            assert page.eval_on_selector("body", "b => b.className") == "rep", "the rep link opens the representative look"
            assert "প্রতিনিধি" in page.inner_text(".top"), page.inner_text(".top")
            page.screenshot(path=f"{SHOTS}/g1-verify-bn.png")
            page.fill("#last4", "0000")
            page.click("#btn_verify")
            page.wait_for_selector(".flash.err")
            assert "সংখ্যা মেলেনি" in page.inner_text("#app")
            page.fill("#last4", "6789")
            page.click("#btn_verify")
            page.wait_for_selector("#f_name_en")

            # ---- form: values from the sheet, Bengali labels, name shown in English (no Arabic name given)
            assert page.input_value("#f_name_en") == "Md Rahim"
            assert "Md Rahim" in page.inner_text("h1")
            assert "পূর্ণ নাম" in page.inner_text("#app")
            assert page.locator(".veh").first.is_hidden(), "vehicle fields hidden until a vehicle is chosen"
            page.select_option("#f_vehicle_type", "سيارة شخصية")
            assert page.locator(".veh").first.is_visible()
            page.screenshot(path=f"{SHOTS}/g2-form-bn.png")

            # ---- switch language keeps what was typed
            page.fill("#f_city", "Jeddah")
            page.click("text=اردو")
            assert page.eval_on_selector("html", "e => [e.lang, e.dir]") == ["ur", "rtl"]
            assert page.input_value("#f_city") == "Jeddah"
            page.screenshot(path=f"{SHOTS}/g3-form-ur.png")
            page.click("text=English")

            # ---- fill the rest, attach 5 big photos, submit
            page.fill("#f_mobile", "٠٥١١١١١١١١")
            page.select_option("#f_app_name", "كيتا ماركت")
            page.fill("#f_app_id", "KM-778899")
            page.select_option("#f_location_consent", "نعم")
            page.select_option("#f_license_type", "دراجة نارية")
            page.fill("#f_license_no", "1020304050")
            page.fill("#f_license_expiry", "2029-05-05")
            page.fill("#f_plate_no", "ABC 1234")
            page.fill("#f_registration_expiry", "2027-05-05")
            page.fill("#f_iqama_profession", "Delivery driver")
            page.fill("#f_emergency_phone", "+880 1712-345678")
            sizes = {}
            for i, k in enumerate(["front", "back", "right", "left", "odometer"]):
                path = photo(os.path.join(SHOTS, f"_p{k}.jpg"), color=(20 * i + 40, 80, 150))
                sizes[k] = os.path.getsize(path)
                page.set_input_files(f"#f_photo_{k}", path)
            page.check("#f_consent")
            page.click("#btn_submit")
            page.wait_for_selector("text=Thank you", timeout=30000)
            assert "Thank you" in page.inner_text("#app"), page.inner_text("#app")[:300]
            page.screenshot(path=f"{SHOTS}/g4-done.png")

            # ---- what the "sheet" and "Drive" now contain
            s = state()
            e = s["emp1"]
            assert e["الحالة"] == "بانتظار المراجعة", e["الحالة"]
            assert e["رقم الجوال (05xxxxxxxx)"] == "0511111111", e["رقم الجوال (05xxxxxxxx)"]
            assert e["المدينة"] == "Jeddah"
            assert e["جوال الطوارئ"] == "+8801712345678"
            assert s["rep1"]["رقم الأيدي (ID) في التطبيق"] == "KM-778899"
            assert s["rep1"]["التطبيق الذي يعمل فيه"] == "كيتا ماركت"
            assert e["نوع رخصة القيادة"] == "دراجة نارية", e
            assert e["صورة العداد (رابط أو اسم الملف)"].startswith("https://drive.google.com/file/d/")
            assert len(s["files"]) == 5, len(s["files"])
            for f in s["files"]:
                img = Image.open(io.BytesIO(base64.b64decode(f["b64"])))
                assert img.format == "JPEG" and max(img.size) <= 1280, (f["name"], img.size)
                assert f["size"] < 400_000, f["size"]            # was several MB before resizing
            print("photo sizes uploaded (bytes):", [f["size"] for f in s["files"]], "originals:", list(sizes.values())[:2])

            # ---- a page visitor cannot run HR functions through google.script.run
            page.goto(f"{base}?t={rep}")
            page.wait_for_selector("#last4")
            res = page.evaluate("""() => new Promise((resolve) => {
                google.script.run.withSuccessHandler(() => resolve('ran')).withFailureHandler((e) => resolve('refused:' + e.message)).prepareLinks();
            })""")
            assert res.startswith("refused:"), res
            res2 = page.evaluate("""() => new Promise((resolve) => {
                google.script.run.withSuccessHandler(() => resolve('ran')).withFailureHandler((e) => resolve('refused:' + e.message)).findByToken_('x');
            })""")
            assert res2.startswith("refused:"), res2

            # ---- staff member (Indian): English by nationality; the vehicle part exists for everyone but stays folded away
            page.goto(f"{base}?t={staff}")
            page.wait_for_selector("#last4")
            assert page.eval_on_selector("html", "e => e.lang") == "en"
            page.fill("#last4", "1111")
            page.click("#btn_verify")
            page.wait_for_selector("#f_name_en")
            assert page.eval_on_selector("body", "b => b.className") == "emp" and "Employee form" in page.inner_text(".top")
            assert page.locator("#f_vehicle_type").count() == 1 and page.locator("#f_photo_front").is_hidden()
            assert page.locator("h2.part").count() == 2, "employee part + vehicle part (no rep part for staff)"
            page.select_option("#f_vehicle_type", "Company motorcycle")
            assert page.locator("#f_photo_odometer").is_visible() and page.locator("#f_license_type").is_visible()
            page.click("#btn_submit")                              # consent not given -> errors, nothing breaks
            page.wait_for_selector(".error")
            assert "This field is required" in page.inner_text("#app")
            b.close()
    finally:
        server.terminate()
    assert not problems, problems
    print("E2E OK. Screenshots in", SHOTS)


if __name__ == "__main__":
    main()
