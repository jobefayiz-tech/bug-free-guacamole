"""Single source of truth for every field the system collects.

The employee form, HR edit form, Excel import/export, validation, masking and
the "what is still missing" calculation are all driven from FIELDS below.
Header text in `xlsx` must match tools/make_template.py (a test enforces it).
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

OPTIONS = {
    "gender": ["ذكر", "أنثى"],
    "marital": ["أعزب", "متزوج", "مطلق", "أرمل"],
    "id_type": ["هوية وطنية", "إقامة"],
    "contract_type": ["غير محدد المدة", "محدد المدة", "عمل مؤقت"],
    "employment_status": ["على رأس العمل", "في إجازة", "منتهية خدمته"],
    "education": ["أقل من الثانوية", "ثانوية", "دبلوم", "بكالوريوس", "ماجستير", "دكتوراه"],
    "relation": ["أب", "أم", "زوج/زوجة", "أخ/أخت", "ابن/ابنة", "قريب آخر", "صديق"],
    "bank": [
        "مصرف الراجحي", "البنك الأهلي السعودي", "بنك الرياض", "مصرف الإنماء",
        "بنك البلاد", "بنك الجزيرة", "البنك السعودي الأول", "البنك العربي الوطني",
        "البنك السعودي الفرنسي", "البنك السعودي للاستثمار", "بنك stc", "أخرى",
    ],
    "vehicle": ["سيارة الشركة", "سيارة شخصية", "دراجة نارية للشركة", "دراجة نارية شخصية", "بدون مركبة"],
    "license_type": ["نقل خفيف", "دراجة نارية"],
    "yesno": ["نعم", "لا"],
    "app": ["كيتا فود", "كيتا ماركت", "نينجا", "تويو", "هنقرستيشن", "مرسول"],
}

# suggestions for free-text fields (not enforced; employees may type anything)
DATALISTS = {
    "nationality": [
        "سعودي", "مصري", "يمني", "سوداني", "سوري", "أردني", "فلسطيني", "لبناني", "عراقي",
        "مغربي", "تونسي", "جزائري", "هندي", "بنغلاديشي", "باكستاني",
    ],
}

VEHICLE_VALUES = ("سيارة الشركة", "سيارة شخصية", "دراجة نارية للشركة", "دراجة نارية شخصية")

SECTIONS = [
    ("personal", "البيانات الشخصية"),
    ("contact", "التواصل والعنوان"),
    ("emergency", "جهة اتصال الطوارئ"),
    ("job", "بيانات الوظيفة"),
    ("bank", "البيانات البنكية"),
    ("rep", "بيانات المندوب"),
    ("vehicle", "الرخصة والمركبة"),
    ("app", "العمل في التطبيق"),
    ("photos", "صور المركبة والعداد"),
    ("consent", "الموافقة"),
]


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    xlsx: str
    section: str
    kind: str = "text"      # text date select phone id iban email photo
    required: bool = False
    options: str = ""        # key into OPTIONS for kind=select
    owner: str = "employee"  # "employee" fills it, "hr" fills it (read-only in the portal)
    rep_only: bool = False
    sensitive: bool = False
    vehicle: bool = False    # required only when the rep has a vehicle
    hint: str = ""
    datalist: str = ""       # key into DATALISTS: suggestions for a free-text field


F = Field
FIELDS = [
    # --- personal
    F("name_ar", "الاسم الكامل (عربي)", "الاسم الكامل (عربي)", "personal", hint="اختياري"),
    F("name_en", "الاسم الكامل (إنجليزي)", "الاسم الكامل (إنجليزي)", "personal", required=True,
      hint="كما في الإقامة أو الجواز"),
    F("nationality", "الجنسية", "الجنسية", "personal", required=True, datalist="nationality"),
    F("gender", "الجنس", "الجنس", "personal", "select", True, "gender"),
    F("birth_date", "تاريخ الميلاد", "تاريخ الميلاد", "personal", "date", True, sensitive=True, hint="ميلادي: سنة-شهر-يوم"),
    F("marital", "الحالة الاجتماعية", "الحالة الاجتماعية", "personal", "select", False, "marital"),
    F("id_type", "نوع الهوية", "نوع الهوية", "personal", "select", True, "id_type"),
    F("id_number", "رقم الهوية / الإقامة", "رقم الهوية / الإقامة (10 أرقام)", "personal", "id", True, sensitive=True, hint="10 أرقام"),
    F("id_expiry", "تاريخ انتهاء الهوية / الإقامة", "تاريخ انتهاء الهوية / الإقامة", "personal", "date", True, hint="ميلادي: سنة-شهر-يوم"),
    F("iqama_profession", "المهنة في الإقامة", "المهنة في الإقامة (للمقيمين)", "personal",
      hint="كما هي مكتوبة في الإقامة (بالعربية أو الإنجليزية)"),
    F("passport_no", "رقم الجواز", "رقم الجواز (للمقيمين)", "personal", sensitive=True),
    F("passport_expiry", "تاريخ انتهاء الجواز", "تاريخ انتهاء الجواز", "personal", "date"),
    F("education", "المؤهل العلمي", "المؤهل العلمي", "personal", "select", False, "education"),
    # --- contact
    F("mobile", "رقم الجوال", "رقم الجوال (05xxxxxxxx)", "contact", "phone", True, hint="مثال: 0512345678"),
    F("email", "البريد الإلكتروني", "البريد الإلكتروني", "contact", "email"),
    F("city", "المدينة", "المدينة", "contact", required=True),
    F("national_address", "العنوان الوطني", "العنوان الوطني (اختياري)", "contact"),
    # --- emergency
    F("emergency_name", "اسم جهة اتصال الطوارئ", "اسم جهة اتصال الطوارئ", "emergency", required=True),
    F("emergency_relation", "صلة القرابة", "صلة القرابة", "emergency", "select", True, "relation"),
    F("emergency_phone", "جوال الطوارئ", "جوال الطوارئ", "emergency", "phone_intl", True,
      hint="إن كان خارج السعودية فاكتب رمز الدولة، مثل +91"),
    # --- job (filled by HR)
    F("job_title", "المسمى الوظيفي", "المسمى الوظيفي", "job", required=True, owner="hr"),
    F("department", "الإدارة / القسم", "الإدارة / القسم", "job", required=True, owner="hr"),
    F("work_location", "مقر العمل", "مقر العمل (الفرع / المدينة)", "job", required=True, owner="hr"),
    F("manager_emp_no", "الرقم الوظيفي للمدير المباشر", "الرقم الوظيفي للمدير المباشر", "job", required=True, owner="hr"),
    F("start_date", "تاريخ المباشرة", "تاريخ المباشرة", "job", "date", True, owner="hr"),
    F("contract_type", "نوع العقد", "نوع العقد", "job", "select", False, "contract_type", owner="hr"),
    F("employment_status", "حالة الموظف", "حالة الموظف", "job", "select", True, "employment_status", owner="hr"),
    # --- bank
    F("bank_name", "اسم البنك", "اسم البنك", "bank", "select", False, "bank"),
    F("iban", "رقم الآيبان", "رقم الآيبان (24 خانة تبدأ بـ SA)", "bank", "iban", sensitive=True, hint="24 خانة تبدأ بـ SA"),
    # --- rep (filled by HR)
    F("rep_code", "كود المندوب", "كود المندوب", "rep", required=True, owner="hr", rep_only=True),
    F("region", "المنطقة / المدينة المسؤول عنها", "المنطقة / المدينة المسؤول عنها", "rep", required=True, owner="hr", rep_only=True),
    F("route", "خط السير / القطاع", "خط السير / القطاع", "rep", owner="hr", rep_only=True),
    F("supervisor_emp_no", "الرقم الوظيفي للمشرف", "الرقم الوظيفي للمشرف المباشر", "rep", required=True, owner="hr", rep_only=True),
    # --- vehicle
    F("vehicle_type", "نوع المركبة", "نوع المركبة", "vehicle", "select", False, "vehicle", rep_only=True),
    F("license_type", "نوع رخصة القيادة", "نوع رخصة القيادة", "vehicle", "select", False, "license_type", rep_only=True, vehicle=True),
    F("license_no", "رقم رخصة القيادة", "رقم رخصة القيادة", "vehicle", rep_only=True, vehicle=True, sensitive=True),
    F("license_expiry", "تاريخ انتهاء الرخصة", "تاريخ انتهاء الرخصة", "vehicle", "date", rep_only=True, vehicle=True),
    F("plate_no", "رقم اللوحة", "رقم اللوحة", "vehicle", rep_only=True, vehicle=True, hint="كما في الاستمارة"),
    F("registration_expiry", "تاريخ انتهاء الاستمارة", "تاريخ انتهاء الاستمارة", "vehicle", "date", rep_only=True, vehicle=True),
    F("device_no", "رقم الجهاز / الشريحة", "رقم الجهاز / الشريحة المخصصة", "vehicle", rep_only=True),
    # --- app
    F("app_name", "التطبيق الذي تعمل فيه", "التطبيق الذي يعمل فيه", "app", "select", True, "app", rep_only=True),
    F("app_id", "رقم الأيدي (ID) في التطبيق", "رقم الأيدي (ID) في التطبيق", "app", required=True, rep_only=True),
    # --- photos
    F("photo_front", "صورة المركبة - الأمام", "صورة المركبة - الأمام (رابط أو اسم الملف)", "photos", "photo", rep_only=True, vehicle=True),
    F("photo_back", "صورة المركبة - الخلف", "صورة المركبة - الخلف (رابط أو اسم الملف)", "photos", "photo", rep_only=True, vehicle=True),
    F("photo_right", "صورة المركبة - اليمين", "صورة المركبة - اليمين (رابط أو اسم الملف)", "photos", "photo", rep_only=True, vehicle=True),
    F("photo_left", "صورة المركبة - اليسار", "صورة المركبة - اليسار (رابط أو اسم الملف)", "photos", "photo", rep_only=True, vehicle=True),
    F("photo_odometer", "صورة العداد", "صورة العداد (رابط أو اسم الملف)", "photos", "photo", rep_only=True, vehicle=True,
      hint="صورة لوحة العدادات تُظهر قراءة المسافة"),
    # --- consent
    F("location_consent", "موافقة على مشاركة الموقع أثناء ساعات العمل", "موافقة على مشاركة الموقع أثناء ساعات العمل", "consent", "select", True, "yesno", rep_only=True),
    F("consent", "أوافق على جمع بياناتي ومعالجتها لأغراض العمل", "موافقة الموظف على معالجة بياناته", "consent", "select", True, "yesno"),
]

BY_KEY = {f.key: f for f in FIELDS}
PHOTO_KEYS = [f.key for f in FIELDS if f.kind == "photo"]
EXPIRY_KEYS = [
    ("id_expiry", "الهوية / الإقامة"),
    ("passport_expiry", "الجواز"),
    ("license_expiry", "رخصة القيادة"),
    ("registration_expiry", "استمارة المركبة"),
]
# the employee decides these, never HR/Excel
CONSENT_KEYS = ("consent", "location_consent")

EMP_NO_XLSX = "الرقم الوظيفي"


def display_name(data, fallback=""):
    """Arabic name if given, otherwise the English one (non-Arabic speakers often leave Arabic empty)."""
    return data.get("name_ar") or data.get("name_en") or fallback


def fields_for(emp_is_rep):
    return [f for f in FIELDS if emp_is_rep or not f.rep_only]


def has_vehicle(data):
    return data.get("vehicle_type") in VEHICLE_VALUES


def is_required(f, data, is_rep):
    if f.rep_only and not is_rep:
        return False
    if f.vehicle:
        return has_vehicle(data)
    if f.key == "iqama_profession":
        return data.get("id_type") == "إقامة"
    return f.required


def missing(data, photos, is_rep, owner=None):
    """Keys of required fields that are still empty. owner limits to 'employee' or 'hr'."""
    out = []
    for f in fields_for(is_rep):
        if owner and f.owner != owner:
            continue
        if not is_required(f, data, is_rep):
            continue
        if f.kind == "photo":
            if f.key not in photos:
                out.append(f.key)
        elif not data.get(f.key):
            out.append(f.key)
    return out


# ---------------------------------------------------------------- cleaning
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize(text):
    return re.sub(r"\s+", " ", str(text).translate(_DIGITS)).strip()


def parse_date(text):
    text = normalize(text)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def iban_ok(iban):
    if not re.fullmatch(r"SA\d{22}", iban):
        return False
    moved = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def clean(f, raw, today=None):
    """Return (value, error). Empty input is always valid (requiredness is checked elsewhere)."""
    value = normalize(raw) if raw is not None else ""
    if not value:
        return "", None
    today = today or date.today()
    if f.kind == "select":
        if value not in OPTIONS[f.options]:
            return value, "اختر من القائمة"
    elif f.kind == "date":
        d = parse_date(value)
        if d is None:
            return value, "تاريخ غير صحيح، اكتبه بصيغة سنة-شهر-يوم"
        low, high = date(1990, 1, 1), date(2100, 12, 31)
        if f.key == "birth_date":
            low, high = date(1930, 1, 1), today - timedelta(days=14 * 365)
        if not low <= d <= high:
            return value, "التاريخ خارج النطاق المعقول"
        value = d.isoformat()
    elif f.kind == "phone":
        digits = re.sub(r"[\s\-]", "", value)
        if digits.startswith("+966"):
            digits = "0" + digits[4:]
        elif digits.startswith("00966"):
            digits = "0" + digits[5:]
        elif digits.startswith("966"):
            digits = "0" + digits[3:]
        elif re.fullmatch(r"5\d{8}", digits):
            digits = "0" + digits
        if not re.fullmatch(r"05\d{8}", digits):
            return value, "رقم الجوال يجب أن يكون بصيغة 05xxxxxxxx"
        value = digits
    elif f.kind == "phone_intl":
        digits = re.sub(r"[\s\-().]", "", value)
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        if re.fullmatch(r"(0?5\d{8}|9665\d{8})", digits):  # Saudi mobile typed without +
            digits = "+966" + digits[-9:]
        if not re.fullmatch(r"\+?\d{8,15}", digits):
            return value, "رقم الهاتف غير صحيح (مع رمز الدولة إن كان خارج السعودية)"
        value = digits
    elif f.kind == "id":
        if not re.fullmatch(r"[12]\d{9}", value):
            return value, "يجب أن يكون 10 أرقام ويبدأ بـ 1 أو 2"
    elif f.kind == "iban":
        value = value.replace(" ", "").upper()
        if not iban_ok(value):
            return value, "رقم الآيبان غير صحيح (SA ثم 22 رقمًا)"
    elif f.kind == "email":
        value = value.lower()
        if not _EMAIL.match(value):
            return value, "بريد إلكتروني غير صحيح"
    else:
        if len(value) > 200:
            return value[:200], "النص أطول من المسموح"
    return value, None


def mask(f, value):
    """Display-safe form of a sensitive value."""
    if not value or not f.sensitive:
        return value
    if f.key == "birth_date":
        return value[:4] + "-••-••"
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * (len(value) - 4) + value[-4:]
