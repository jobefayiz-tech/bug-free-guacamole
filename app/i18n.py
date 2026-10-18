"""Employee-portal translations: Arabic (canonical), English, Urdu, Bengali, Hindi.

Stored values are always the Arabic canonical text (so HR sees consistent data);
only what the employee reads on screen is translated. Missing translations fall back
to English, then to Arabic. NOTE: the Urdu/Bengali/Hindi text should be reviewed by a native speaker.
"""
from .fields import BY_KEY, DATALISTS, GROUPS, OPTIONS, SECTIONS

LANGS = {
    "ar": ("العربية", "rtl"),
    "en": ("English", "ltr"),
    "ur": ("اردو", "rtl"),
    "bn": ("বাংলা", "ltr"),
    "hi": ("हिन्दी", "ltr"),
}
ORDER = ("ar", "en", "ur", "bn", "hi")  # tuple order used by the tables below (after the Arabic text)

# nationality (Arabic) -> language to send the link in when HR picks "automatic"
NAT_LANG = {"بنغلاديشي": "bn", "باكستاني": "ur", "هندي": "en"}


def _t(*vals):
    """(en, ur, bn, hi)"""
    return dict(zip(("en", "ur", "bn", "hi"), vals))


UI = {
    "title": ("بياناتي الوظيفية", _t("My employment details", "میری ملازمت کی معلومات", "আমার চাকরির তথ্য", "मेरी नौकरी की जानकारी")),
    "title_rep": ("بيانات المندوب", _t("Delivery representative details", "ڈلیوری نمائندے کی معلومات", "ডেলিভারি প্রতিনিধির তথ্য", "डिलीवरी प्रतिनिधि की जानकारी")),
    "kind_emp": ("نموذج الموظف", _t("Employee form", "ملازم کا فارم", "কর্মীর ফর্ম", "कर्मचारी फ़ॉर्म")),
    "kind_rep": ("نموذج المندوب", _t("Representative form", "نمائندے کا فارم", "প্রতিনিধির ফর্ম", "प्रतिनिधि फ़ॉर्म")),
    "welcome": ("مرحبًا", _t("Welcome", "خوش آمدید", "স্বাগতম", "स्वागत है")),
    "verify_text": ("للتأكد أنك صاحب الرابط، اكتب آخر 4 أرقام من رقم هويتك أو إقامتك، أو من رقم جوالك.",
                    _t("To confirm it is you, enter the last 4 digits of your ID / Iqama number or of your mobile number.",
                       "تصدیق کے لیے اپنے شناختی کارڈ / اقامہ نمبر یا موبائل نمبر کے آخری 4 ہندسے لکھیں۔",
                       "আপনিই যে সঠিক ব্যক্তি তা নিশ্চিত করতে আপনার আইডি / ইকামা নম্বর অথবা মোবাইল নম্বরের শেষ ৪টি সংখ্যা লিখুন।",
                       "पुष्टि के लिए अपने आईडी / इक़ामा नंबर या मोबाइल नंबर के आख़िरी 4 अंक लिखें।")),
    "vehicle_note": ("إن كانت لديك مركبة تستخدمها في العمل فاختر نوعها لتظهر خانات الرخصة والصور. وإن لم تكن لديك فاختر «بدون مركبة».",
                     _t("If you use a vehicle for work, choose its type to show the licence and photo fields. If you have none, choose “No vehicle”.",
                        "اگر آپ کام کے لیے گاڑی استعمال کرتے ہیں تو اس کی قسم منتخب کریں تاکہ لائسنس اور تصاویر کے خانے ظاہر ہوں۔ اگر نہیں ہے تو «کوئی گاڑی نہیں» منتخب کریں۔",
                        "কাজে যানবাহন ব্যবহার করলে এর ধরন বেছে নিন, তাহলে লাইসেন্স ও ছবির ঘর দেখা যাবে। না থাকলে «কোনো যানবাহন নেই» বেছে নিন।",
                        "यदि आप काम के लिए वाहन इस्तेमाल करते हैं तो उसका प्रकार चुनें, ताकि लाइसेंस और फोटो के खाने दिखें। न हो तो «कोई वाहन नहीं» चुनें।")),
    "last4": ("آخر 4 أرقام", _t("Last 4 digits", "آخری 4 ہندسے", "শেষ ৪টি সংখ্যা", "आख़िरी 4 अंक")),
    "continue": ("متابعة", _t("Continue", "جاری رکھیں", "এগিয়ে যান", "आगे बढ़ें")),
    "mismatch": ("الأرقام غير مطابقة", _t("Digits do not match", "ہندسے مماثل نہیں", "সংখ্যা মেলেনি", "अंक मेल नहीं खाते")),
    "locked": ("تجاوزت عدد المحاولات. حاول بعد 15 دقيقة.",
               _t("Too many attempts. Try again in 15 minutes.", "بہت زیادہ کوششیں۔ 15 منٹ بعد دوبارہ کوشش کریں۔",
                  "অনেকবার চেষ্টা করা হয়েছে। ১৫ মিনিট পরে আবার চেষ্টা করুন।", "बहुत अधिक प्रयास। 15 मिनट बाद फिर कोशिश करें।")),
    "returned": ("أعادت الموارد البشرية بياناتك للتعديل:",
                 _t("HR has returned your details for correction:", "HR نے آپ کی معلومات درستی کے لیے واپس بھیجی ہیں:",
                    "এইচআর আপনার তথ্য সংশোধনের জন্য ফেরত পাঠিয়েছে:", "एचआर ने आपकी जानकारी सुधार के लिए लौटाई है:")),
    "approved": ("بياناتك معتمدة. إن غيّرت أي شيء فسيُرسَل للمراجعة من جديد.",
                 _t("Your details are approved. If you change anything it will be sent for review again.",
                    "آپ کی معلومات منظور ہو چکی ہیں۔ کوئی تبدیلی کریں گے تو دوبارہ جائزے کے لیے جائے گی۔",
                    "আপনার তথ্য অনুমোদিত। কিছু পরিবর্তন করলে আবার পর্যালোচনায় যাবে।",
                    "आपकी जानकारी स्वीकृत है। कुछ बदलने पर वह फिर समीक्षा के लिए जाएगी।")),
    "submitted": ("أُرسلت بياناتك وتنتظر مراجعة الموارد البشرية. يمكنك تعديلها وإعادة الإرسال.",
                  _t("Your details were sent and are waiting for HR review. You can edit and resend.",
                     "آپ کی معلومات بھیج دی گئی ہیں اور HR کے جائزے کی منتظر ہیں۔ آپ ترمیم کر کے دوبارہ بھیج سکتے ہیں۔",
                     "আপনার তথ্য পাঠানো হয়েছে এবং এইচআর পর্যালোচনার অপেক্ষায় আছে। সম্পাদনা করে আবার পাঠাতে পারেন।",
                     "आपकी जानकारी भेज दी गई है और एचआर की समीक्षा की प्रतीक्षा में है। आप बदलकर दोबारा भेज सकते हैं।")),
    "saved": ("تم حفظ ما أدخلته.", _t("Your entries were saved.", "آپ کی درج کردہ معلومات محفوظ ہو گئیں۔",
                                     "আপনার দেওয়া তথ্য সংরক্ষিত হয়েছে।", "आपकी दर्ज की गई जानकारी सहेज ली गई।")),
    "fix_errors": ("بعض الحقول تحتاج تصحيحًا، راجع الحقول المظللة بالأحمر.",
                   _t("Some fields need correction. Check the fields marked in red.",
                      "کچھ خانوں کو درست کرنا ہے۔ سرخ نشان والے خانے دیکھیں۔",
                      "কিছু ঘর সংশোধন করতে হবে। লাল চিহ্নিত ঘরগুলো দেখুন।", "कुछ फ़ील्ड ठीक करने हैं। लाल निशान वाले फ़ील्ड देखें।")),
    "remaining": ("المتبقي لإرسال بياناتك:", _t("Remaining before you can submit:", "بھیجنے سے پہلے باقی:",
                                                 "জমা দেওয়ার আগে বাকি:", "भेजने से पहले शेष:")),
    "remaining_unit": ("حقل/صورة", _t("fields/photos", "خانے/تصاویر", "ঘর/ছবি", "फ़ील्ड/फोटो")),
    "select": ("— اختر —", _t("— Select —", "— منتخب کریں —", "— বেছে নিন —", "— चुनें —")),
    "hr_filled": ("(تُدخلها الموارد البشرية)", _t("(filled in by HR)", "(HR کی طرف سے بھری جاتی ہے)",
                                                   "(এইচআর পূরণ করে)", "(एचआर द्वारा भरी जाती है)")),
    "save_draft": ("حفظ مؤقتًا", _t("Save draft", "عارضی طور پر محفوظ کریں", "খসড়া সংরক্ষণ", "ड्राफ़्ट सहेजें")),
    "submit": ("إرسال للاعتماد", _t("Submit", "جمع کرائیں", "জমা দিন", "जमा करें")),
    "submit_update": ("حفظ وإرسال للمراجعة", _t("Save and send for review", "محفوظ کریں اور جائزے کے لیے بھیجیں",
                                                 "সংরক্ষণ করে পর্যালোচনায় পাঠান", "सहेजें और समीक्षा के लिए भेजें")),
    "thanks": ("شكرًا", _t("Thank you", "شکریہ", "ধন্যবাদ", "धन्यवाद")),
    "done_text": ("وصلت بياناتك إلى الموارد البشرية وستُراجَع قريبًا.",
                  _t("Your details reached HR and will be reviewed soon.", "آپ کی معلومات HR تک پہنچ گئی ہیں اور جلد جائزہ لیا جائے گا۔",
                     "আপনার তথ্য এইচআর-এর কাছে পৌঁছেছে, শীঘ্রই পর্যালোচনা করা হবে।",
                     "आपकी जानकारी एचआर तक पहुँच गई है और जल्द ही समीक्षा की जाएगी।")),
    "done_hint": ("يمكنك العودة لهذا الرابط في أي وقت لتحديث بياناتك.",
                  _t("You can return to this link any time to update your details.",
                     "آپ اپنی معلومات اپ ڈیٹ کرنے کے لیے کسی بھی وقت اسی لنک پر واپس آ سکتے ہیں۔",
                     "আপনার তথ্য হালনাগাদ করতে যেকোনো সময় এই লিংকে ফিরে আসতে পারেন।",
                     "आप अपनी जानकारी अपडेट करने के लिए कभी भी इसी लिंक पर लौट सकते हैं।")),
    "back": ("رجوع لبياناتي", _t("Back to my details", "میری معلومات پر واپس", "আমার তথ্যে ফিরে যান", "मेरी जानकारी पर लौटें")),
    "language": ("اللغة", _t("Language", "زبان", "ভাষা", "भाषा")),
    # used by the Google Apps Script version (single-page, talks to the server with JavaScript)
    "bad_link": ("الرابط غير صحيح أو انتهت صلاحيته. اطلب رابطًا جديدًا من الموارد البشرية.",
                 _t("This link is not valid or has expired. Ask HR for a new link.",
                    "یہ لنک درست نہیں یا اس کی میعاد ختم ہو گئی ہے۔ HR سے نیا لنک مانگیں۔",
                    "লিংকটি সঠিক নয় বা মেয়াদ শেষ। এইচআর-এর কাছ থেকে নতুন লিংক চান।",
                    "लिंक मान्य नहीं है या समाप्त हो गया है। एचआर से नया लिंक माँगें।")),
    "loading": ("جارٍ التحميل…", _t("Loading…", "لوڈ ہو رہا ہے…", "লোড হচ্ছে…", "लोड हो रहा है…")),
    "saving": ("جارٍ الحفظ…", _t("Saving…", "محفوظ ہو رہا ہے…", "সংরক্ষণ হচ্ছে…", "सहेजा जा रहा है…")),
    "uploading": ("جارٍ رفع الصور…", _t("Uploading photos…", "تصاویر اپ لوڈ ہو رہی ہیں…", "ছবি আপলোড হচ্ছে…", "फोटो अपलोड हो रही हैं…")),
    "uploaded": ("✓ تم رفع الصورة", _t("✓ Photo uploaded", "✓ تصویر اپ لوڈ ہو گئی", "✓ ছবি আপলোড হয়েছে", "✓ फोटो अपलोड हो गई")),
    "network_error": ("تعذّر الاتصال. تحقق من الإنترنت وحاول مرة أخرى.",
                      _t("Connection problem. Check your internet and try again.",
                         "کنکشن میں مسئلہ۔ انٹرنیٹ چیک کریں اور دوبارہ کوشش کریں۔",
                         "সংযোগে সমস্যা। ইন্টারনেট দেখে আবার চেষ্টা করুন।",
                         "कनेक्शन में समस्या। इंटरनेट जाँचें और फिर कोशिश करें।")),
    "session_expired": ("انتهت الجلسة. أدخل الأرقام الأربعة مرة أخرى.",
                        _t("Session expired. Enter the 4 digits again.", "سیشن ختم ہو گیا۔ 4 ہندسے دوبارہ لکھیں۔",
                           "সেশন শেষ। ৪টি সংখ্যা আবার লিখুন।", "सत्र समाप्त। 4 अंक फिर से लिखें।")),
}

SECTION_TITLES = {
    "personal": _t("Personal details", "ذاتی معلومات", "ব্যক্তিগত তথ্য", "व्यक्तिगत जानकारी"),
    "contact": _t("Contact & address", "رابطہ اور پتہ", "যোগাযোগ ও ঠিকানা", "संपर्क और पता"),
    "emergency": _t("Emergency contact", "ہنگامی رابطہ", "জরুরি যোগাযোগ", "आपातकालीन संपर्क"),
    "job": _t("Job details", "ملازمت کی تفصیلات", "চাকরির বিবরণ", "नौकरी का विवरण"),
    "bank": _t("Bank details", "بینک کی تفصیلات", "ব্যাংকের তথ্য", "बैंक विवरण"),
    "rep": _t("Representative details", "نمائندے کی تفصیلات", "প্রতিনিধির তথ্য", "प्रतिनिधि विवरण"),
    "vehicle": _t("Licence & vehicle", "لائسنس اور گاڑی", "লাইসেন্স ও যানবাহন", "लाइसेंस और वाहन"),
    "app": _t("Work app", "کام کی ایپ", "কাজের অ্যাপ", "काम का ऐप"),
    "photos": _t("Vehicle & odometer photos", "گاڑی اور اوڈومیٹر کی تصاویر", "গাড়ি ও ওডোমিটারের ছবি", "वाहन और ओडोमीटर की फोटो"),
    "consent": _t("Consent", "رضامندی", "সম্মতি", "सहमति"),
}

GROUP_TITLES = {
    "employee": _t("Employee details", "ملازم کی معلومات", "কর্মীর তথ্য", "कर्मचारी की जानकारी"),
    "vehicle": _t("Vehicle & photos (if you have one)", "گاڑی اور تصاویر (اگر ہو)", "যানবাহন ও ছবি (থাকলে)", "वाहन और फोटो (यदि हो)"),
    "rep": _t("Delivery representative details (reps only)", "ڈلیوری نمائندے کی معلومات (صرف نمائندوں کے لیے)",
              "ডেলিভারি প্রতিনিধির তথ্য (শুধু প্রতিনিধিদের জন্য)", "डिलीवरी प्रतिनिधि की जानकारी (केवल प्रतिनिधियों के लिए)"),
}

FIELD_LABELS = {
    "name_ar": _t("Full name (Arabic)", "پورا نام (عربی)", "পূর্ণ নাম (আরবি)", "पूरा नाम (अरबी)"),
    "name_en": _t("Full name (English, as in Iqama / Passport)", "پورا نام (انگریزی، جیسا اقامہ / پاسپورٹ میں ہے)",
                  "পূর্ণ নাম (ইংরেজি, ইকামা / পাসপোর্ট অনুযায়ী)", "पूरा नाम (अंग्रेज़ी, इक़ामा / पासपोर्ट के अनुसार)"),
    "nationality": _t("Nationality", "قومیت", "জাতীয়তা", "राष्ट्रीयता"),
    "gender": _t("Gender", "جنس", "লিঙ্গ", "लिंग"),
    "birth_date": _t("Date of birth", "تاریخ پیدائش", "জন্ম তারিখ", "जन्म तिथि"),
    "marital": _t("Marital status", "ازدواجی حیثیت", "বৈবাহিক অবস্থা", "वैवाहिक स्थिति"),
    "id_type": _t("ID type", "شناخت کی قسم", "পরিচয়পত্রের ধরন", "पहचान का प्रकार"),
    "id_number": _t("ID / Iqama number", "شناختی کارڈ / اقامہ نمبر", "আইডি / ইকামা নম্বর", "आईडी / इक़ामा नंबर"),
    "id_expiry": _t("ID / Iqama expiry date", "شناختی کارڈ / اقامہ کی میعاد ختم ہونے کی تاریخ",
                    "আইডি / ইকামার মেয়াদ শেষের তারিখ", "आईडी / इक़ामा की समाप्ति तिथि"),
    "iqama_profession": _t("Profession on Iqama", "اقامہ میں درج پیشہ", "ইকামায় উল্লিখিত পেশা", "इक़ामा में लिखा पेशा"),
    "passport_no": _t("Passport number", "پاسپورٹ نمبر", "পাসপোর্ট নম্বর", "पासपोर्ट नंबर"),
    "passport_expiry": _t("Passport expiry date", "پاسپورٹ کی میعاد ختم ہونے کی تاریخ", "পাসপোর্টের মেয়াদ শেষের তারিখ", "पासपोर्ट की समाप्ति तिथि"),
    "education": _t("Education", "تعلیم", "শিক্ষাগত যোগ্যতা", "शिक्षा"),
    "mobile": _t("Mobile number (Saudi)", "موبائل نمبر (سعودی)", "মোবাইল নম্বর (সৌদি)", "मोबाइल नंबर (सऊदी)"),
    "email": _t("Email", "ای میل", "ইমেইল", "ईमेल"),
    "city": _t("City", "شہر", "শহর", "शहर"),
    "national_address": _t("National address (optional)", "قومی پتہ (اختیاری)", "জাতীয় ঠিকানা (ঐচ্ছিক)", "राष्ट्रीय पता (वैकल्पिक)"),
    "emergency_name": _t("Emergency contact name", "ہنگامی رابطے کا نام", "জরুরি যোগাযোগের নাম", "आपातकालीन संपर्क का नाम"),
    "emergency_relation": _t("Relationship", "رشتہ", "সম্পর্ক", "रिश्ता"),
    "emergency_phone": _t("Emergency contact phone", "ہنگامی رابطے کا فون نمبر", "জরুরি যোগাযোগের ফোন নম্বর", "आपातकालीन संपर्क का फ़ोन नंबर"),
    "job_title": _t("Job title", "عہدہ", "পদবি", "पद"),
    "department": _t("Department", "شعبہ", "বিভাগ", "विभाग"),
    "work_location": _t("Work location", "کام کی جگہ", "কর্মস্থল", "कार्यस्थल"),
    "manager_emp_no": _t("Direct manager employee no.", "براہ راست مینیجر کا ملازم نمبر", "সরাসরি ম্যানেজারের কর্মচারী নম্বর", "सीधे प्रबंधक का कर्मचारी नंबर"),
    "start_date": _t("Start date", "ملازمت شروع ہونے کی تاریخ", "যোগদানের তারিখ", "कार्यारंभ तिथि"),
    "contract_type": _t("Contract type", "معاہدے کی قسم", "চুক্তির ধরন", "अनुबंध का प्रकार"),
    "employment_status": _t("Employment status", "ملازمت کی حیثیت", "চাকরির অবস্থা", "नौकरी की स्थिति"),
    "bank_name": _t("Bank name", "بینک کا نام", "ব্যাংকের নাম", "बैंक का नाम"),
    "iban": _t("IBAN", "آئی بین (IBAN)", "আইবান (IBAN)", "आईबैन (IBAN)"),
    "rep_code": _t("Rep code", "نمائندے کا کوڈ", "প্রতিনিধি কোড", "प्रतिनिधि कोड"),
    "region": _t("Region / city covered", "متعلقہ علاقہ / شہر", "দায়িত্বপ্রাপ্ত অঞ্চল / শহর", "ज़िम्मेदार क्षेत्र / शहर"),
    "route": _t("Route / sector", "روٹ / سیکٹر", "রুট / সেক্টর", "रूट / सेक्टर"),
    "supervisor_emp_no": _t("Supervisor employee no.", "سپروائزر کا ملازم نمبر", "সুপারভাইজারের কর্মচারী নম্বর", "पर्यवेक्षक का कर्मचारी नंबर"),
    "vehicle_type": _t("Vehicle type", "گاڑی کی قسم", "যানবাহনের ধরন", "वाहन का प्रकार"),
    "license_type": _t("Driving licence type", "ڈرائیونگ لائسنس کی قسم", "ড্রাইভিং লাইসেন্সের ধরন", "ड्राइविंग लाइसेंस का प्रकार"),
    "license_no": _t("Driving licence number", "ڈرائیونگ لائسنس نمبر", "ড্রাইভিং লাইসেন্স নম্বর", "ड्राइविंग लाइसेंस नंबर"),
    "license_expiry": _t("Licence expiry date", "لائسنس کی میعاد ختم ہونے کی تاریخ", "লাইসেন্সের মেয়াদ শেষের তারিখ", "लाइसेंस की समाप्ति तिथि"),
    "plate_no": _t("Plate number", "نمبر پلیٹ", "নম্বর প্লেট", "नंबर प्लेट"),
    "registration_expiry": _t("Vehicle registration (Istimara) expiry date", "گاڑی کی رجسٹریشن (استمارہ) کی میعاد ختم ہونے کی تاریخ",
                              "গাড়ির রেজিস্ট্রেশন (ইস্তিমারা) মেয়াদ শেষের তারিখ", "वाहन पंजीकरण (इस्तिमारा) की समाप्ति तिथि"),
    "device_no": _t("Device / SIM number", "ڈیوائس / سم نمبر", "ডিভাইস / সিম নম্বর", "डिवाइस / सिम नंबर"),
    "app_name": _t("App you work with", "جس ایپ میں آپ کام کرتے ہیں", "আপনি যে অ্যাপে কাজ করেন", "जिस ऐप में आप काम करते हैं"),
    "app_id": _t("Your ID in the app", "ایپ میں آپ کی آئی ڈی", "অ্যাপে আপনার আইডি", "ऐप में आपकी आईडी"),
    "photo_front": _t("Vehicle photo - front", "گاڑی کی تصویر - سامنے", "গাড়ির ছবি - সামনে", "वाहन की फोटो - सामने"),
    "photo_back": _t("Vehicle photo - back", "گاڑی کی تصویر - پیچھے", "গাড়ির ছবি - পিছনে", "वाहन की फोटो - पीछे"),
    "photo_right": _t("Vehicle photo - right side", "گاڑی کی تصویر - دائیں طرف", "গাড়ির ছবি - ডান দিক", "वाहन की फोटो - दाईं ओर"),
    "photo_left": _t("Vehicle photo - left side", "گاڑی کی تصویر - بائیں طرف", "গাড়ির ছবি - বাম দিক", "वाहन की फोटो - बाईं ओर"),
    "photo_odometer": _t("Odometer photo", "اوڈومیٹر کی تصویر", "ওডোমিটারের ছবি", "ओडोमीटर की फोटो"),
    "location_consent": _t("I agree to share my location during working hours", "میں کام کے اوقات میں اپنی لوکیشن شیئر کرنے سے متفق ہوں",
                           "আমি কাজের সময় আমার অবস্থান শেয়ার করতে সম্মত", "मैं काम के घंटों में अपनी लोकेशन साझा करने के लिए सहमत हूँ"),
    "consent": _t("I agree to the collection and processing of my data for work purposes",
                  "میں کام کے مقاصد کے لیے اپنا ڈیٹا جمع اور استعمال کیے جانے سے متفق ہوں",
                  "আমি কাজের উদ্দেশ্যে আমার তথ্য সংগ্রহ ও ব্যবহারে সম্মত",
                  "मैं कार्य-उद्देश्यों के लिए अपने डेटा के संग्रह और उपयोग के लिए सहमत हूँ"),
}

HINTS = {
    "name_ar": _t("Optional", "اختیاری", "ঐচ্ছিক", "वैकल्पिक"),
    "name_en": _t("Exactly as printed on your Iqama or passport", "بالکل ویسے لکھیں جیسا اقامہ یا پاسپورٹ پر ہے",
                  "ইকামা বা পাসপোর্টে যেভাবে লেখা আছে ঠিক সেভাবে লিখুন", "इक़ामा या पासपोर्ट पर जैसा छपा है ठीक वैसा लिखें"),
    "birth_date": _t("Gregorian (AD) date", "عیسوی تاریخ", "ইংরেজি (খ্রিস্টাব্দ) তারিখ", "ईसवी तारीख"),
    "id_expiry": _t("Gregorian (AD) date", "عیسوی تاریخ", "ইংরেজি (খ্রিস্টাব্দ) তারিখ", "ईसवी तारीख"),
    "id_number": _t("10 digits", "10 ہندسے", "১০টি সংখ্যা", "10 अंक"),
    "iqama_profession": _t("Write it as printed on the Iqama (Arabic or English)", "اقامہ میں جیسا لکھا ہے ویسا لکھیں (عربی یا انگریزی)",
                           "ইকামায় যেমন লেখা আছে তেমন লিখুন (আরবি বা ইংরেজি)", "इक़ामा में जैसा लिखा है वैसा लिखें (अरबी या अंग्रेज़ी)"),
    "mobile": _t("Example: 0512345678", "مثال: 0512345678", "উদাহরণ: 0512345678", "उदाहरण: 0512345678"),
    "emergency_phone": _t("If outside Saudi Arabia, include the country code, e.g. +91 / +92 / +880",
                          "سعودی عرب سے باہر ہو تو ملک کا کوڈ لکھیں، مثلاً +92",
                          "সৌদির বাইরে হলে দেশের কোড দিন, যেমন +880", "सऊदी से बाहर हो तो देश का कोड लिखें, जैसे +91"),
    "iban": _t("24 characters starting with SA", "SA سے شروع ہونے والے 24 حروف", "SA দিয়ে শুরু ২৪টি অক্ষর", "SA से शुरू होने वाले 24 अक्षर"),
    "plate_no": _t("As written on the registration (Istimara)", "جیسا استمارہ میں لکھا ہے", "ইস্তিমারায় যেমন লেখা আছে", "इस्तिमारा में जैसा लिखा है"),
    "photo_odometer": _t("Photo of the dashboard showing the distance reading", "ڈیش بورڈ کی تصویر جس میں فاصلے کی ریڈنگ نظر آئے",
                         "ড্যাশবোর্ডের ছবি যেখানে দূরত্বের রিডিং দেখা যায়", "डैशबोर्ड की फोटो जिसमें दूरी की रीडिंग दिखे"),
}

OPTION_LABELS = {
    "ذكر": _t("Male", "مرد", "পুরুষ", "पुरुष"), "أنثى": _t("Female", "عورت", "মহিলা", "महिला"),
    "أعزب": _t("Single", "غیر شادی شدہ", "অবিবাহিত", "अविवाहित"), "متزوج": _t("Married", "شادی شدہ", "বিবাহিত", "विवाहित"),
    "مطلق": _t("Divorced", "طلاق یافتہ", "তালাকপ্রাপ্ত", "तलाकशुदा"),
    "أرمل": _t("Widowed", "بیوہ / رنڈوا", "বিধবা / বিপত্নীক", "विधवा / विधुर"),
    "هوية وطنية": _t("National ID", "قومی شناختی کارڈ", "জাতীয় পরিচয়পত্র", "राष्ट्रीय पहचान पत्र"),
    "إقامة": _t("Iqama (residence permit)", "اقامہ", "ইকামা", "इक़ामा"),
    "غير محدد المدة": _t("Unlimited term", "غیر معینہ مدت", "অনির্দিষ্ট মেয়াদ", "अनिश्चित अवधि"),
    "محدد المدة": _t("Fixed term", "مقررہ مدت", "নির্দিষ্ট মেয়াদ", "निश्चित अवधि"),
    "عمل مؤقت": _t("Temporary", "عارضی", "অস্থায়ী", "अस्थायी"),
    "على رأس العمل": _t("Active", "کام پر", "কর্মরত", "कार्यरत"), "في إجازة": _t("On leave", "چھٹی پر", "ছুটিতে", "छुट्टी पर"),
    "منتهية خدمته": _t("Service ended", "ملازمت ختم", "চাকরি শেষ", "सेवा समाप्त"),
    "أقل من الثانوية": _t("Below secondary", "سیکنڈری سے کم", "মাধ্যমিকের নিচে", "माध्यमिक से कम"),
    "ثانوية": _t("Secondary", "سیکنڈری", "মাধ্যমিক", "माध्यमिक"), "دبلوم": _t("Diploma", "ڈپلومہ", "ডিপ্লোমা", "डिप्लोमा"),
    "بكالوريوس": _t("Bachelor's", "بیچلر", "স্নাতক", "स्नातक"), "ماجستير": _t("Master's", "ماسٹرز", "স্নাতকোত্তর", "स्नातकोत्तर"),
    "دكتوراه": _t("Doctorate", "ڈاکٹریٹ", "ডক্টরেট", "डॉक्टरेट"),
    "أب": _t("Father", "والد", "বাবা", "पिता"), "أم": _t("Mother", "والدہ", "মা", "माता"),
    "زوج/زوجة": _t("Spouse", "شریکِ حیات", "স্বামী / স্ত্রী", "पति / पत्नी"),
    "أخ/أخت": _t("Brother / Sister", "بھائی / بہن", "ভাই / বোন", "भाई / बहन"),
    "ابن/ابنة": _t("Son / Daughter", "بیٹا / بیٹی", "ছেলে / মেয়ে", "बेटा / बेटी"),
    "قريب آخر": _t("Other relative", "دوسرا رشتہ دار", "অন্য আত্মীয়", "अन्य रिश्तेदार"), "صديق": _t("Friend", "دوست", "বন্ধু", "मित्र"),
    "أخرى": _t("Other", "دیگر", "অন্যান্য", "अन्य"),
    "سيارة الشركة": _t("Company car", "کمپنی کی گاڑی", "কোম্পানির গাড়ি", "कंपनी की गाड़ी"),
    "سيارة شخصية": _t("Personal car", "ذاتی گاڑی", "ব্যক্তিগত গাড়ি", "निजी गाड़ी"),
    "دراجة نارية للشركة": _t("Company motorcycle", "کمپنی کی موٹر سائیکل", "কোম্পানির মোটরসাইকেল", "कंपनी की मोटरसाइकिल"),
    "دراجة نارية شخصية": _t("Personal motorcycle", "ذاتی موٹر سائیکل", "ব্যক্তিগত মোটরসাইকেল", "निजी मोटरसाइकिल"),
    "نقل خفيف": _t("Light transport", "لائٹ ٹرانسپورٹ", "লাইট ট্রান্সপোর্ট", "लाइट ट्रांसपोर्ट"),
    "دراجة نارية": _t("Motorcycle", "موٹر سائیکل", "মোটরসাইকেল", "मोटरसाइकिल"),
    "بدون مركبة": _t("No vehicle", "کوئی گاڑی نہیں", "কোনো যানবাহন নেই", "कोई वाहन नहीं"),
    "نعم": _t("Yes", "ہاں", "হ্যাঁ", "हाँ"), "لا": _t("No", "نہیں", "না", "नहीं"),
    # delivery apps / banks: English names are universal
    "كيتا فود": {"en": "Keeta Food"}, "كيتا ماركت": {"en": "Keeta Market"}, "نينجا": {"en": "Ninja"},
    "تويو": {"en": "ToYou"}, "هنقرستيشن": {"en": "HungerStation"}, "مرسول": {"en": "Mrsool"},
    "مصرف الراجحي": {"en": "Al Rajhi Bank"}, "البنك الأهلي السعودي": {"en": "Saudi National Bank (SNB)"},
    "بنك الرياض": {"en": "Riyad Bank"}, "مصرف الإنماء": {"en": "Alinma Bank"}, "بنك البلاد": {"en": "Bank Albilad"},
    "بنك الجزيرة": {"en": "Bank AlJazira"}, "البنك السعودي الأول": {"en": "Saudi Awwal Bank (SAB)"},
    "البنك العربي الوطني": {"en": "Arab National Bank"}, "البنك السعودي الفرنسي": {"en": "Banque Saudi Fransi"},
    "البنك السعودي للاستثمار": {"en": "Saudi Investment Bank"}, "بنك stc": {"en": "stc bank"},
    # nationalities (suggestions)
    "سعودي": {"en": "Saudi"}, "مصري": {"en": "Egyptian"}, "يمني": {"en": "Yemeni"}, "سوداني": {"en": "Sudanese"},
    "سوري": {"en": "Syrian"}, "أردني": {"en": "Jordanian"}, "فلسطيني": {"en": "Palestinian"}, "لبناني": {"en": "Lebanese"},
    "عراقي": {"en": "Iraqi"}, "مغربي": {"en": "Moroccan"}, "تونسي": {"en": "Tunisian"}, "جزائري": {"en": "Algerian"},
    "هندي": _t("Indian", "بھارتی", "ভারতীয়", "भारतीय"), "بنغلاديشي": _t("Bangladeshi", "بنگلہ دیشی", "বাংলাদেশি", "बांग्लादेशी"),
    "باكستاني": _t("Pakistani", "پاکستانی", "পাকিস্তানি", "पाकिस्तानी"),
}

MESSAGES = {  # error / validation messages produced by the code (keys are the Arabic text)
    "اختر من القائمة": _t("Choose from the list", "فہرست میں سے منتخب کریں", "তালিকা থেকে বেছে নিন", "सूची में से चुनें"),
    "تاريخ غير صحيح، اكتبه بصيغة سنة-شهر-يوم": _t("Invalid date", "غلط تاریخ", "ভুল তারিখ", "गलत तारीख"),
    "التاريخ خارج النطاق المعقول": _t("Date is out of the valid range", "تاریخ درست حد سے باہر ہے", "তারিখ সঠিক সীমার বাইরে", "तारीख मान्य सीमा से बाहर है"),
    "رقم الجوال يجب أن يكون بصيغة 05xxxxxxxx": _t("Mobile number must look like 05xxxxxxxx", "موبائل نمبر 05xxxxxxxx کی شکل میں ہونا چاہیے",
                                                  "মোবাইল নম্বর 05xxxxxxxx ফরম্যাটে হতে হবে", "मोबाइल नंबर 05xxxxxxxx प्रारूप में होना चाहिए"),
    "رقم الهاتف غير صحيح (مع رمز الدولة إن كان خارج السعودية)": _t("Invalid phone number (add the country code if outside Saudi Arabia)",
                                                                  "فون نمبر غلط ہے (سعودی عرب سے باہر ہو تو ملک کا کوڈ لکھیں)",
                                                                  "ফোন নম্বর ভুল (সৌদির বাইরে হলে দেশের কোড দিন)",
                                                                  "फ़ोन नंबर गलत है (सऊदी से बाहर हो तो देश का कोड जोड़ें)"),
    "يجب أن يكون 10 أرقام ويبدأ بـ 1 أو 2": _t("Must be 10 digits starting with 1 or 2", "10 ہندسے ہوں اور 1 یا 2 سے شروع ہوں",
                                              "১০টি সংখ্যা হতে হবে এবং ১ বা ২ দিয়ে শুরু", "10 अंक हों और 1 या 2 से शुरू हों"),
    "رقم الآيبان غير صحيح (SA ثم 22 رقمًا)": _t("Invalid IBAN (SA followed by 22 digits)", "آئی بین غلط ہے (SA کے بعد 22 ہندسے)",
                                                "আইবান ভুল (SA এর পর ২২টি সংখ্যা)", "आईबैन गलत है (SA के बाद 22 अंक)"),
    "بريد إلكتروني غير صحيح": _t("Invalid email", "ای میل غلط ہے", "ইমেইল ভুল", "ईमेल गलत है"),
    "النص أطول من المسموح": _t("Text is too long", "متن بہت لمبا ہے", "লেখা অনেক বড়", "पाठ बहुत लंबा है"),
    "هذا الحقل مطلوب": _t("This field is required", "یہ خانہ ضروری ہے", "এই ঘরটি পূরণ আবশ্যক", "यह फ़ील्ड आवश्यक है"),
    "الملف ليس صورة صالحة (استخدم JPG أو PNG)": _t("Not a valid image (use JPG or PNG)", "درست تصویر نہیں (JPG یا PNG استعمال کریں)",
                                                    "সঠিক ছবি নয় (JPG বা PNG ব্যবহার করুন)", "मान्य फोटो नहीं (JPG या PNG उपयोग करें)"),
    "صيغة الصورة غير مدعومة (استخدم JPG أو PNG)": _t("Unsupported image format (use JPG or PNG)", "تصویر کا فارمیٹ تعاون یافتہ نہیں (JPG یا PNG)",
                                                      "ছবির ফরম্যাট সমর্থিত নয় (JPG বা PNG)", "फोटो का प्रारूप समर्थित नहीं (JPG या PNG)"),
}

WA_MESSAGE = {
    "ar": "السلام عليكم {name}، نرجو تعبئة بياناتك الوظيفية عبر هذا الرابط الشخصي (لا تشاركه مع أحد): {link}",
    "en": "Hello {name}, please fill in your employment details using this personal link (do not share it with anyone): {link}",
    "ur": "السلام علیکم {name}، براہ کرم اس ذاتی لنک سے اپنی ملازمت کی معلومات بھریں (یہ لنک کسی کے ساتھ شیئر نہ کریں): {link}",
    "bn": "আসসালামু আলাইকুম {name}, অনুগ্রহ করে এই ব্যক্তিগত লিংক দিয়ে আপনার চাকরির তথ্য পূরণ করুন (লিংকটি কারও সাথে শেয়ার করবেন না): {link}",
    "hi": "नमस्ते {name}, कृपया इस निजी लिंक से अपनी नौकरी की जानकारी भरें (यह लिंक किसी से साझा न करें): {link}",
}


class Tr:
    """Translator for one language, handed to templates."""

    def __init__(self, lang):
        self.lang = lang if lang in LANGS else "ar"
        self.dir = LANGS[self.lang][1]

    def _pick(self, ar, table):
        if self.lang == "ar":
            return ar
        return table.get(self.lang) or table.get("en") or ar

    def t(self, key):
        ar, table = UI[key]
        return self._pick(ar, table)

    def label(self, f):
        table = FIELD_LABELS.get(f.key)
        return self._pick(f.label, table) if table else f.label

    def hint(self, f):
        table = HINTS.get(f.key)
        return self._pick(f.hint, table) if table else (f.hint if self.lang == "ar" else "")

    def opt(self, value):
        table = OPTION_LABELS.get(value)
        return self._pick(value, table) if table else value

    def group(self, key):
        return self._pick(dict(GROUPS)[key], GROUP_TITLES[key])

    def section(self, key):
        ar = dict(SECTIONS)[key]
        return self._pick(ar, SECTION_TITLES[key])

    def msg(self, text):
        table = MESSAGES.get(text)
        return self._pick(text, table) if table else text

    def datalist(self, key):
        return [(v, self.opt(v)) for v in DATALISTS[key]]


def pick_language(requested, fallback="ar"):
    return requested if requested in LANGS else fallback


def whatsapp_text(lang, name, link):
    return WA_MESSAGE.get(lang, WA_MESSAGE["ar"]).format(name=name, link=link)


def auto_language(data):
    return NAT_LANG.get(data.get("nationality", ""), "ar")


def _selfcheck():
    """Every translatable thing must have all the languages we promise (checked by tests)."""
    missing = []
    for key in FIELD_LABELS:
        assert key in BY_KEY, key
        for lang in ("en", "ur", "bn", "hi"):
            if lang not in FIELD_LABELS[key]:
                missing.append(("label", key, lang))
    for group in OPTIONS.values():
        for v in group:
            if v not in OPTION_LABELS:
                missing.append(("option", v, "en"))
    return missing
