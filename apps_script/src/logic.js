// Pure validation logic. Mirrors app/fields.py (a parity test checks both give the same answers).
// Used by the server (Code.gs) and by the browser page (Index.html), so both validate identically.
function makeLogic_(CONFIG) {
  const FIELDS = CONFIG.fields;
  const BY_KEY = {};
  FIELDS.forEach(function (f) { BY_KEY[f.key] = f; });

  const DIGITS = {'٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'};

  function normalize(text) {
    return String(text).replace(/[٠-٩۰-۹]/g, function (c) { return DIGITS[c]; }).replace(/\s+/g, ' ').trim();
  }

  // returns ms (UTC midnight) for a valid calendar date, otherwise null
  function ymd(y, m, d) {
    const ms = Date.UTC(y, m - 1, d);
    const dt = new Date(ms);
    return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d ? ms : null;
  }

  function parseDate(text) {
    text = normalize(text);
    let m = /^(\d{4})([-\/])(\d{1,2})\2(\d{1,2})$/.exec(text);
    if (m) { const ms = ymd(+m[1], +m[3], +m[4]); if (ms !== null) return ms; }
    m = /^(\d{1,2})([-\/])(\d{1,2})\2(\d{4})$/.exec(text);
    if (m) { const ms = ymd(+m[4], +m[3], +m[1]); if (ms !== null) return ms; }
    return null;
  }

  function iso(ms) {
    const d = new Date(ms);
    const p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getUTCFullYear() + '-' + p(d.getUTCMonth() + 1) + '-' + p(d.getUTCDate());
  }

  function todayMs(today) {
    if (typeof today === 'string') return parseDate(today);
    const t = today || new Date();
    return Date.UTC(t.getFullYear(), t.getMonth(), t.getDate());
  }

  function ibanOk(value) {
    if (!/^SA\d{22}$/.test(value)) return false;
    const moved = value.slice(4) + value.slice(0, 4);
    let rem = 0;
    for (let i = 0; i < moved.length; i++) {
      const n = parseInt(moved[i], 36); // digits stay, letters A=10..Z=35
      rem = (n < 10 ? rem * 10 + n : rem * 100 + n) % 97;
    }
    return rem === 1;
  }

  const DAY = 86400000;

  // -> [value, error|null]; empty input is always valid (requiredness is checked elsewhere)
  function clean(f, raw, today) {
    let value = (raw === null || raw === undefined) ? '' : normalize(raw);
    if (!value) return ['', null];
    const now = todayMs(today);
    if (f.kind === 'select') {
      if (CONFIG.options[f.options].indexOf(value) < 0) return [value, 'اختر من القائمة'];
    } else if (f.kind === 'date') {
      const ms = parseDate(value);
      if (ms === null) return [value, 'تاريخ غير صحيح، اكتبه بصيغة سنة-شهر-يوم'];
      let low = Date.UTC(1990, 0, 1), high = Date.UTC(2100, 11, 31);
      if (f.key === 'birth_date') { low = Date.UTC(1930, 0, 1); high = now - 14 * 365 * DAY; }
      if (ms < low || ms > high) return [value, 'التاريخ خارج النطاق المعقول'];
      value = iso(ms);
    } else if (f.kind === 'phone') {
      let digits = value.replace(/[\s\-]/g, '');
      if (digits.indexOf('+966') === 0) digits = '0' + digits.slice(4);
      else if (digits.indexOf('00966') === 0) digits = '0' + digits.slice(5);
      else if (digits.indexOf('966') === 0) digits = '0' + digits.slice(3);
      else if (/^5\d{8}$/.test(digits)) digits = '0' + digits;
      if (!/^05\d{8}$/.test(digits)) return [value, 'رقم الجوال يجب أن يكون بصيغة 05xxxxxxxx'];
      value = digits;
    } else if (f.kind === 'phone_intl') {
      let digits = value.replace(/[\s\-().]/g, '');
      if (digits.indexOf('00') === 0) digits = '+' + digits.slice(2);
      if (/^(0?5\d{8}|9665\d{8})$/.test(digits)) digits = '+966' + digits.slice(-9);
      if (!/^\+?\d{8,15}$/.test(digits)) return [value, 'رقم الهاتف غير صحيح (مع رمز الدولة إن كان خارج السعودية)'];
      value = digits;
    } else if (f.kind === 'id') {
      if (!/^[12]\d{9}$/.test(value)) return [value, 'يجب أن يكون 10 أرقام ويبدأ بـ 1 أو 2'];
    } else if (f.kind === 'iban') {
      value = value.replace(/ /g, '').toUpperCase();
      if (!ibanOk(value)) return [value, 'رقم الآيبان غير صحيح (SA ثم 22 رقمًا)'];
    } else if (f.kind === 'email') {
      value = value.toLowerCase();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)) return [value, 'بريد إلكتروني غير صحيح'];
    } else if (value.length > 200) {
      return [value.slice(0, 200), 'النص أطول من المسموح'];
    }
    return [value, null];
  }

  function hasVehicle(data) { return CONFIG.vehicleValues.indexOf(data.vehicle_type) >= 0; }

  function isRequired(f, data, isRep) {
    if (f.repOnly && !isRep) return false;
    if (f.vehicle) return hasVehicle(data);
    if (f.key === 'vehicle_type') return !!isRep;   // a rep must answer (it may be "no vehicle"); other staff may skip it
    if (f.key === 'iqama_profession') return data.id_type === 'إقامة';
    return !!f.required;
  }

  function fieldsFor(isRep) {
    return FIELDS.filter(function (f) { return isRep || !f.repOnly; });
  }

  // keys of required fields still empty; photos is an object {key: truthy}
  function missing(data, photos, isRep, owner) {
    const out = [];
    fieldsFor(isRep).forEach(function (f) {
      if (owner && f.owner !== owner) return;
      if (!isRequired(f, data, isRep)) return;
      if (f.kind === 'photo') { if (!photos[f.key]) out.push(f.key); }
      else if (!data[f.key]) out.push(f.key);
    });
    return out;
  }

  function displayName(data, fallback) {
    return data.name_ar || data.name_en || fallback || '';
  }

  return {normalize: normalize, parseDate: parseDate, clean: clean, isRequired: isRequired, missing: missing,
    fieldsFor: fieldsFor, displayName: displayName, hasVehicle: hasVehicle, ibanOk: ibanOk, BY_KEY: BY_KEY, iso: iso};
}

if (typeof module !== 'undefined') { module.exports = {makeLogic_: makeLogic_}; }
