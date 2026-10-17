// ===================================================================================
// Server side (Google Apps Script). The Google Sheet is the database.
//  - Employee page:   doGet + api* functions (called from Index.html with google.script.run)
//  - HR menu:         onOpen + the admin functions (guarded: they only run from the Sheet UI)
// Functions whose name ends with "_" are private: the web page cannot call them.
// ===================================================================================
const LG = makeLogic_(CONFIG);

const SHEET_EMP = 'الموظفون';
const SHEET_REP = 'المناديب';
const SHEET_DASH = 'لوحة المتابعة';
const SHEET_ALERTS = 'تنبيهات الانتهاء';
const EMP_NO_HEADER = 'الرقم الوظيفي';
const ST = {UNOPENED: CONFIG.statuses.unopened, DRAFT: CONFIG.statuses.draft, SUBMITTED: CONFIG.statuses.submitted,
  RETURNED: CONFIG.statuses.returned, APPROVED: CONFIG.statuses.approved};
// system columns appended after the template columns of the employees sheet
const SYS = [
  ['token', 'الرمز السري'], ['status', 'الحالة'], ['note', 'ملاحظة المراجعة'], ['opened', 'فُتح في'],
  ['submitted', 'أُرسل في'], ['updated', 'آخر تحديث'], ['missing', 'حقول ناقصة'], ['isRep', 'مندوب؟'],
  ['lang', 'لغة الرابط'], ['consentAt', 'وقت الموافقة'], ['link', 'رابط الموظف'], ['wa', 'إرسال واتساب']
];
const SYS_HEADER = {};
SYS.forEach(function (p) { SYS_HEADER[p[0]] = p[1]; });
const MAX_FAILS = 5;
const LOCK_SECONDS = 900;
const SESSION_SECONDS = 21600;   // 6 hours (CacheService maximum)
const MAX_PHOTO_CHARS = 6 * 1024 * 1024;

// ------------------------------------------------------------------ helpers
function props_() { return PropertiesService.getScriptProperties(); }

let SS_CACHE_ = null;   // one execution = one request, so this never goes stale across requests
function ss_() {
  if (SS_CACHE_) return SS_CACHE_;
  let ss = null;
  try { ss = SpreadsheetApp.getActiveSpreadsheet(); } catch (e) { ss = null; }   // works from the sheet and from onEdit
  if (!ss) {                                                                     // web page requests: open by saved id
    const id = props_().getProperty('SS_ID');
    if (id) ss = SpreadsheetApp.openById(id);
  }
  if (!ss) throw new Error('لم يتم تجهيز الجداول بعد (شغّل: بيانات الموظفين > تجهيز الجداول)');
  SS_CACHE_ = ss;
  return ss;
}

const TZ = 'Asia/Riyadh';
function tz_() { return TZ; }

function stamp_() { return Utilities.formatDate(new Date(), tz_(), 'yyyy-MM-dd HH:mm'); }

function normHeader_(h) { return String(h === null || h === undefined ? '' : h).replace(/\*/g, '').replace(/\s+/g, ' ').trim(); }

function colLetter_(n) {   // 1 -> A
  let s = '';
  while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

function cellText_(v) {
  if (v === null || v === undefined) return '';
  if (Object.prototype.toString.call(v) === '[object Date]') {
    let zone = TZ;
    try { zone = ss_().getSpreadsheetTimeZone() || TZ; } catch (e) { zone = TZ; }
    return Utilities.formatDate(v, zone, 'yyyy-MM-dd');
  }
  return String(v).trim();
}

function table_(name) {
  const sheet = ss_().getSheetByName(name);
  if (!sheet) throw new Error('الورقة غير موجودة: ' + name + ' (شغّل: بيانات الموظفين > تجهيز الجداول)');
  const lastCol = Math.max(sheet.getLastColumn(), 1);
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(normHeader_);
  const cols = {};
  headers.forEach(function (h, i) { if (h && !(h in cols)) cols[h] = i; });
  return {sheet: sheet, headers: headers, cols: cols, lastRow: sheet.getLastRow(), lastCol: lastCol};
}

function col_(t, header) { return t.cols[normHeader_(header)]; }

function sysCol_(t, key) { return col_(t, SYS_HEADER[key]); }

function fieldCol_(t, f) { return col_(t, f.xlsx); }

function newToken_() {
  return Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
}

function safeName_(s) { return String(s).replace(/[^A-Za-z0-9_\-]/g, '_').slice(0, 60) || '_'; }

// ------------------------------------------------------------------ reading / writing one employee
function findRepRow_(empNo) {
  const t = table_(SHEET_REP);
  const c = col_(t, EMP_NO_HEADER);
  if (c === undefined || t.lastRow < 2) return {t: t, row: 0};
  const vals = t.sheet.getRange(2, c + 1, t.lastRow - 1, 1).getValues();
  for (let i = 0; i < vals.length; i++) if (cellText_(vals[i][0]) === empNo) return {t: t, row: i + 2};
  return {t: t, row: 0};
}

function load_(t, row) {
  const raw = t.sheet.getRange(row, 1, 1, t.lastCol).getValues()[0];
  const empNo = cellText_(raw[col_(t, EMP_NO_HEADER)]);
  const data = {};
  FIELDS_PLAIN_.forEach(function (f) {
    const c = fieldCol_(t, f);
    if (c !== undefined) data[f.key] = cellText_(raw[c]);
  });
  const rep = findRepRow_(empNo);
  const flag = cellText_(raw[sysCol_(t, 'isRep')]);
  const isRep = rep.row > 0 || flag === 'نعم';
  const photos = {};
  let repRaw = null;
  if (rep.row > 0) {
    repRaw = rep.t.sheet.getRange(rep.row, 1, 1, rep.t.lastCol).getValues()[0];
    FIELDS_REP_.forEach(function (f) {
      const c = fieldCol_(rep.t, f);
      if (c === undefined) return;
      const v = cellText_(repRaw[c]);
      if (f.kind === 'photo') { if (v) photos[f.key] = v; } else data[f.key] = v;
    });
  }
  return {t: t, row: row, raw: raw, empNo: empNo, data: data, photos: photos, isRep: isRep, rep: rep, repRaw: repRaw,
    status: cellText_(raw[sysCol_(t, 'status')]), note: cellText_(raw[sysCol_(t, 'note')])};
}

const FIELDS_PLAIN_ = CONFIG.fields.filter(function (f) { return !f.repOnly; });
const FIELDS_REP_ = CONFIG.fields.filter(function (f) { return f.repOnly; });

function findByToken_(token) {
  if (typeof token !== 'string' || !/^[0-9a-f]{64}$/.test(token)) return null;   // cheap reject: no sheet read for junk
  const t = table_(SHEET_EMP);
  const c = sysCol_(t, 'token');
  if (c === undefined || t.lastRow < 2) return null;
  const vals = t.sheet.getRange(2, c + 1, t.lastRow - 1, 1).getValues();
  for (let i = 0; i < vals.length; i++) if (vals[i][0] === token) return load_(t, i + 2);
  return null;
}

// writes only the given column indexes of one row, as plain text (keeps leading zeros and ISO dates)
function writeCells_(sheet, row, values, colIdxs) {
  const cols = colIdxs.slice().sort(function (a, b) { return a - b; });
  let i = 0;
  while (i < cols.length) {
    let j = i;
    while (j + 1 < cols.length && cols[j + 1] === cols[j] + 1) j++;
    const range = sheet.getRange(row, cols[i] + 1, 1, j - i + 1);
    range.setNumberFormat('@');
    // a text starting with "=" must never become a spreadsheet formula (defence in depth: the cell is plain text anyway)
    range.setValues([values.slice(cols[i], cols[j] + 1).map(function (v) {
      return typeof v === 'string' && v.charAt(0) === '=' ? ' ' + v : v;
    })]);
    i = j + 1;
  }
}

// persist: changed = {key: value} for plain/rep fields, sys = {sysKey: value}, photoUrls = {photoKey: url}
function persist_(emp, changed, sys, photoUrls) {
  const t = emp.t;
  const raw = emp.raw.slice();
  const touched = [];
  FIELDS_PLAIN_.forEach(function (f) {
    if (f.key in changed) { const c = fieldCol_(t, f); if (c !== undefined) { raw[c] = changed[f.key]; touched.push(c); } }
  });
  Object.keys(sys).forEach(function (k) { const c = sysCol_(t, k); if (c !== undefined) { raw[c] = sys[k]; touched.push(c); } });

  const repChanged = {};
  FIELDS_REP_.forEach(function (f) { if (f.key in changed) repChanged[f.key] = changed[f.key]; });
  const hasRepWrite = Object.keys(repChanged).length > 0 || (photoUrls && Object.keys(photoUrls).length > 0);
  if (emp.isRep && hasRepWrite) {
    let rep = emp.rep;
    const rt = rep.t;
    const empCol = col_(rt, EMP_NO_HEADER);
    const repTouched = [];
    if (rep.row === 0) {                        // first time: create the rep row
      const blank = new Array(rt.lastCol).fill('');
      blank[empCol] = emp.empNo;
      rep = {t: rt, row: Math.max(rt.lastRow, 1) + 1};
      emp.rep = rep;
      emp.repRaw = blank;
      repTouched.push(empCol);
    }
    const rr = emp.repRaw.slice();
    FIELDS_REP_.forEach(function (f) {
      const c = fieldCol_(rt, f);
      if (c === undefined) return;
      if (f.key in repChanged) { rr[c] = repChanged[f.key]; repTouched.push(c); }
      if (photoUrls && f.key in photoUrls) { rr[c] = photoUrls[f.key]; repTouched.push(c); }
    });
    writeCells_(rt.sheet, rep.row, rr, repTouched);
    emp.repRaw = rr;
  }
  writeCells_(t.sheet, emp.row, raw, touched);
  emp.raw = raw;
}

function allMissing_(emp) {
  return LG.missing(emp.data, emp.photos, emp.isRep);
}

// ------------------------------------------------------------------ session / throttling
function cache_() { return CacheService.getScriptCache(); }

function isLocked_(empNo) { return cache_().get('lk:' + empNo) === '1'; }

function failVerify_(empNo) {
  const c = cache_();
  const n = (parseInt(c.get('fc:' + empNo) || '0', 10) || 0) + 1;
  if (n >= MAX_FAILS) { c.put('lk:' + empNo, '1', LOCK_SECONDS); c.remove('fc:' + empNo); }
  else c.put('fc:' + empNo, String(n), LOCK_SECONDS);
}

function newSession_(empNo) {
  const s = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
  cache_().put('s:' + s, empNo, SESSION_SECONDS);
  return s;
}

function fail_(err) {
  console.error(err && err.stack ? err.stack : String(err));
  return {ok: false, error: 'server'};
}

// returns {emp} or {error}
function auth_(token, session) {
  const emp = findByToken_(token);
  if (!emp) return {error: 'bad_link'};
  if (typeof session !== 'string' || cache_().get('s:' + session) !== emp.empNo) return {error: 'session'};
  return {emp: emp};
}

function withLock_(fn) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try { return fn(); } finally { lock.releaseLock(); }
}

// ------------------------------------------------------------------ web app
function doGet(e) {
  const p = (e && e.parameter) || {};
  const tpl = HtmlService.createTemplate(INDEX_HTML);
  tpl.boot = bootJson_({token: String(p.t || ''), lang: String(p.lang || '')});
  return tpl.evaluate()
    .setTitle('بياناتي الوظيفية')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function bootJson_(extra) {
  const obj = {config: CONFIG, token: extra.token, lang: extra.lang};
  return JSON.stringify(obj).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
}

function apiStart(token) {
  try {
    const emp = findByToken_(token);
    if (!emp) return {ok: false, error: 'bad_link'};
    const needVerify = !!emp.data.id_number;
    const res = {ok: true, needVerify: needVerify, locked: isLocked_(emp.empNo),
      name: LG.displayName(emp.data, emp.empNo), nationality: emp.data.nationality || ''};
    if (!needVerify) res.session = newSession_(emp.empNo);
    return res;
  } catch (err) { return fail_(err); }
}

function apiVerify(token, last4) {
  try {
    const emp = findByToken_(token);
    if (!emp) return {ok: false, error: 'bad_link'};
    if (isLocked_(emp.empNo)) return {ok: false, error: 'locked'};
    const idn = emp.data.id_number || '', mob = emp.data.mobile || '';
    const typed = LG.normalize(last4 === null || last4 === undefined ? '' : last4);
    // the ID on file may be wrong (that is why the data is being collected), so the mobile the link was sent to works too
    if (idn && typed.length === 4 && (typed === idn.slice(-4) || (mob && typed === mob.slice(-4)))) {
      cache_().remove('fc:' + emp.empNo);
      return {ok: true, session: newSession_(emp.empNo)};
    }
    failVerify_(emp.empNo);
    return {ok: false, error: isLocked_(emp.empNo) ? 'locked' : 'mismatch'};
  } catch (err) { return fail_(err); }
}

function payload_(emp) {
  return {ok: true, empNo: emp.empNo, isRep: emp.isRep, data: emp.data, photos: Object.keys(emp.photos),
    status: emp.status || ST.UNOPENED, note: emp.note,
    todo: LG.missing(emp.data, emp.photos, emp.isRep, 'employee')};
}

function apiLoad(token, session) {
  try {
    const a = auth_(token, session);
    if (a.error) return {ok: false, error: a.error};
    const emp = a.emp;
    if (!cellText_(emp.raw[sysCol_(emp.t, 'opened')])) {
      withLock_(function () {
        const fresh = findByToken_(token);
        const sys = {opened: stamp_()};
        if (!fresh.status || fresh.status === ST.UNOPENED) { sys.status = ST.DRAFT; emp.status = ST.DRAFT; }
        persist_(fresh, {}, sys, null);
      });
    }
    return payload_(emp);
  } catch (err) { return fail_(err); }
}

// values: {key: string}, consent: boolean for the data-processing checkbox, action: 'draft' | 'submit'
function apiSave(token, session, values, action) {
  try {
    const a = auth_(token, session);
    if (a.error) return {ok: false, error: a.error};
    return withLock_(function () {
      const emp = findByToken_(token);
      values = values || {};
      let act = action === 'submit' ? 'submit' : 'draft';
      if (emp.status === ST.SUBMITTED || emp.status === ST.APPROVED) act = 'submit';
      const editable = LG.fieldsFor(emp.isRep).filter(function (f) { return f.owner === 'employee' && f.kind !== 'photo'; });
      const data = Object.assign({}, emp.data);
      const errors = {};
      const changed = {};
      editable.forEach(function (f) {
        if (f.key === 'consent') { data.consent = values.consent ? 'نعم' : ''; changed.consent = data.consent; return; }
        if (!(f.key in values)) return;
        const r = LG.clean(f, values[f.key]);
        if (r[1]) errors[f.key] = r[1];
        else { data[f.key] = r[0]; changed[f.key] = r[0]; }
      });
      const todo = LG.missing(data, emp.photos, emp.isRep, 'employee');
      const problems = Object.keys(errors).length;
      const sys = {updated: stamp_()};
      if (act === 'submit') {
        todo.forEach(function (k) { if (!errors[k]) errors[k] = 'هذا الحقل مطلوب'; });
      }
      const blocked = Object.keys(errors).length > 0;
      let status = emp.status || ST.DRAFT;
      if (act === 'submit' && !blocked) {
        status = ST.SUBMITTED; sys.submitted = stamp_(); sys.note = '';
      } else if (act === 'submit' && (emp.status === ST.SUBMITTED || emp.status === ST.APPROVED)) {
        status = ST.DRAFT;   // edited but not valid yet: no longer final
      } else if (!emp.status || emp.status === ST.UNOPENED) {
        status = ST.DRAFT;
      }
      sys.status = status;
      if (data.consent === 'نعم' && !cellText_(emp.raw[sysCol_(emp.t, 'consentAt')])) sys.consentAt = stamp_();
      emp.data = data;
      sys.missing = String(LG.missing(data, emp.photos, emp.isRep).length);
      persist_(emp, changed, sys, null);
      return {ok: true, saved: !blocked && problems === 0, submitted: act === 'submit' && !blocked, errors: errors,
        status: status, todo: LG.missing(data, emp.photos, emp.isRep, 'employee')};
    });
  } catch (err) { return fail_(err); }
}

function isJpeg_(bytes) {
  return bytes && bytes.length > 4 && (bytes[0] & 255) === 0xFF && (bytes[1] & 255) === 0xD8 && (bytes[2] & 255) === 0xFF;
}

function photoFolder_(empNo) {
  const rootId = props_().getProperty('PHOTO_FOLDER_ID');
  const root = rootId ? DriveApp.getFolderById(rootId) : DriveApp.createFolder('صور الموظفين');
  if (!rootId) props_().setProperty('PHOTO_FOLDER_ID', root.getId());
  const name = safeName_(empNo);
  const it = root.getFoldersByName(name);
  return it.hasNext() ? it.next() : root.createFolder(name);
}

function apiPhoto(token, session, key, b64) {
  try {
    const a = auth_(token, session);
    if (a.error) return {ok: false, error: a.error};
    if (CONFIG.photoKeys.indexOf(key) < 0) return {ok: false, error: 'bad_request'};
    if (typeof b64 !== 'string' || b64.length > MAX_PHOTO_CHARS) return {ok: false, error: 'too_big'};
    let bytes = null;
    try { bytes = Utilities.base64Decode(b64.replace(/^data:image\/\w+;base64,/, '')); } catch (e) { bytes = null; }
    if (!isJpeg_(bytes)) return {ok: false, error: 'bad_image', message: 'الملف ليس صورة صالحة (استخدم JPG أو PNG)'};
    return withLock_(function () {
      const emp = findByToken_(token);
      if (!emp.isRep) return {ok: false, error: 'bad_request'};
      const folder = photoFolder_(emp.empNo);
      const fname = key + '.jpg';
      const old = folder.getFilesByName(fname);
      while (old.hasNext()) old.next().setTrashed(true);
      const file = folder.createFile(Utilities.newBlob(bytes, 'image/jpeg', fname));
      const photos = Object.assign({}, emp.photos);
      photos[key] = file.getUrl();
      emp.photos = photos;
      const sys = {updated: stamp_(), missing: String(LG.missing(emp.data, photos, emp.isRep).length)};
      persist_(emp, {}, sys, (function () { const o = {}; o[key] = file.getUrl(); return o; })());
      return {ok: true, todo: LG.missing(emp.data, photos, emp.isRep, 'employee')};
    });
  } catch (err) { return fail_(err); }
}


// ------------------------------------------------------------------ HR menu (Sheet UI only)
// SpreadsheetApp.getUi() throws outside the Sheet UI, so a web-page visitor can never run these.
function adminUi_() { return SpreadsheetApp.getUi(); }

const GRID_ROWS = 2000;   // rows pre-formatted for data (1000 staff + headroom)

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('بيانات الموظفين')
    .addItem('① تجهيز الجداول (مرة واحدة)', 'setupSheets')
    .addItem('② تجهيز الروابط وأزرار واتساب', 'prepareLinks')
    .addItem('ضبط رابط النشر', 'setBaseUrl')
    .addSeparator()
    .addItem('تحديث الحقول الناقصة', 'recomputeAll')
    .addItem('تحديث تنبيهات الانتهاء', 'buildAlerts')
    .addItem('إنشاء رابط جديد للصف المحدد', 'regenLinkForRow')
    .addItem('نسخة احتياطية في Drive', 'backupNow')
    .addToUi();
}

function headerRow_(fields, withSys) {
  const row = [EMP_NO_HEADER + ' *'].concat(fields.map(function (f) { return f.xlsx + (f.required ? ' *' : ''); }));
  if (withSys) SYS.forEach(function (p) { row.push(p[1]); });
  return row;
}

function ensureGrid_(sh, rows, cols) {
  if (sh.getMaxRows() < rows) sh.insertRowsAfter(sh.getMaxRows(), rows - sh.getMaxRows());
  if (sh.getMaxColumns() < cols) sh.insertColumnsAfter(sh.getMaxColumns(), cols - sh.getMaxColumns());
}

function ensureSheet_(ss, name, headers) {
  let sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  ensureGrid_(sh, GRID_ROWS + 1, headers.length);
  if (!String(sh.getRange(1, 1).getValue() || '').trim()) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  } else {
    // add any header that is missing (e.g. after an update) at the end
    const have = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0].map(normHeader_);
    headers.forEach(function (h) {
      if (have.indexOf(normHeader_(h)) < 0) {
        const next = sh.getLastColumn() + 1;
        ensureGrid_(sh, GRID_ROWS + 1, next);
        sh.getRange(1, next).setValue(h);
        have.push(normHeader_(h));
      }
    });
  }
  return sh;
}

function setupSheets() {
  const ui = adminUi_();
  const ss = ss_();
  props_().setProperty('SS_ID', ss.getId());
  ensureSheet_(ss, SHEET_EMP, headerRow_(FIELDS_PLAIN_, true));
  ensureSheet_(ss, SHEET_REP, headerRow_(FIELDS_REP_, false));
  SS_CACHE_ = null;
  const et = table_(SHEET_EMP);
  const rt = table_(SHEET_REP);
  [et, rt].forEach(function (t) {
    const rng = t.sheet.getRange(2, 1, GRID_ROWS, t.lastCol);
    rng.setNumberFormat('@');
    rng.setHorizontalAlignment('right');
    t.sheet.setFrozenRows(1);
    t.sheet.setFrozenColumns(1);
    t.sheet.setRightToLeft(true);
    t.sheet.getRange(1, 1, 1, t.lastCol).setFontWeight('bold').setBackground('#1f3a5f').setFontColor('#ffffff')
      .setWrap(true).setHorizontalAlignment('center');
    t.sheet.setRowHeight(1, 48);
    for (let c = 1; c <= t.lastCol; c++) t.sheet.setColumnWidth(c, 130);
  });
  const sc = sysCol_(et, 'status');
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList([ST.UNOPENED, ST.DRAFT, ST.SUBMITTED, ST.RETURNED, ST.APPROVED], true).setAllowInvalid(false).build();
  et.sheet.getRange(2, sc + 1, GRID_ROWS, 1).setDataValidation(rule);
  addExpiryFormatting_(et);
  addExpiryFormatting_(rt);
  buildDashboard_(ss, et);
  if (!props_().getProperty('PHOTO_FOLDER_ID')) props_().setProperty('PHOTO_FOLDER_ID', DriveApp.createFolder('صور الموظفين').getId());
  ui.alert('تم تجهيز الجداول.\nالخطوة التالية: الصق بيانات الموظفين في ورقة «' + SHEET_EMP + '» وبيانات المناديب في ورقة «' + SHEET_REP +
    '» ابتداءً من الصف 2، ثم انشر التطبيق وشغّل «② تجهيز الروابط».');
}

function addExpiryFormatting_(t) {
  const rules = [];
  CONFIG.expiryKeys.forEach(function (k) {
    const f = LG.BY_KEY[k[0]];
    const c = fieldCol_(t, f);
    if (c === undefined) return;
    const L = colLetter_(c + 1);
    const range = t.sheet.getRange(2, c + 1, GRID_ROWS, 1);
    const v = 'IFERROR(IF(ISNUMBER(' + L + '2),' + L + '2,DATEVALUE(' + L + '2)),99999)';
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=AND(' + L + '2<>"",' + v + '<TODAY())').setBackground('#f4c7c3').setRanges([range]).build());
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=AND(' + L + '2<>"",' + v + '<TODAY()+30)').setBackground('#fce8b2').setRanges([range]).build());
  });
  t.sheet.setConditionalFormatRules(rules);
}

function buildDashboard_(ss, et) {
  let sh = ss.getSheetByName(SHEET_DASH);
  if (!sh) sh = ss.insertSheet(SHEET_DASH);
  sh.setRightToLeft(true);
  const S = colLetter_(sysCol_(et, 'status') + 1);
  const E = colLetter_(col_(et, EMP_NO_HEADER) + 1);
  const M = colLetter_(sysCol_(et, 'missing') + 1);
  const R = colLetter_(sysCol_(et, 'isRep') + 1);
  const q = "'" + SHEET_EMP + "'!";
  const cnt = function (st) { return '=COUNTIF(' + q + S + '2:' + S + ',"' + st + '")'; };
  const labels = [
    ['المؤشر'], ['إجمالي الموظفين'], [ST.UNOPENED], [ST.DRAFT], [ST.SUBMITTED], [ST.RETURNED], [ST.APPROVED],
    ['سجلات فيها حقول ناقصة'], ['المناديب'], ['نسبة الاعتماد']
  ];
  const formulas = [
    ['=COUNTA(' + q + E + '2:' + E + ')'],
    [cnt(ST.UNOPENED)],
    [cnt(ST.DRAFT)],
    [cnt(ST.SUBMITTED)],
    [cnt(ST.RETURNED)],
    [cnt(ST.APPROVED)],
    // the missing-count cells are plain text ("14"), which COUNTIF(">0") does not count, so compare as text
    ['=SUMPRODUCT(--(LEN(' + q + M + '2:' + M + ')>0),--(' + q + M + '2:' + M + '<>"0"),--(' + q + M + '2:' + M + '<>0))'],
    ['=COUNTIF(' + q + R + '2:' + R + ',"نعم")'],
    ['=IFERROR(B7/B2,0)']
  ];
  // Labels are plain text (setValues); only real formulas go through setFormulas, which would read a label as a formula.
  sh.getRange(1, 1, labels.length, 1).setValues(labels);
  sh.getRange(1, 2).setValue('العدد');
  sh.getRange(2, 2, formulas.length, 1).setFormulas(formulas);
  sh.getRange(10, 2).setNumberFormat('0%');
  sh.getRange(1, 1, 1, 2).setFontWeight('bold').setBackground('#1f3a5f').setFontColor('#ffffff');
  sh.setColumnWidth(1, 220);
}

function baseUrl_() {
  const saved = props_().getProperty('BASE_URL');
  if (saved) return saved;
  try { const u = ScriptApp.getService().getUrl(); if (u) return u; } catch (e) { /* not deployed yet */ }
  return '';
}

function setBaseUrl() {
  const ui = adminUi_();
  const r = ui.prompt('رابط النشر', 'الصق رابط تطبيق الويب (ينتهي بـ /exec):', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  const url = String(r.getResponseText() || '').trim();
  if (!/^https:\/\/script\.google\.com\/.+\/exec$/.test(url)) {
    ui.alert('الرابط غير صحيح. يجب أن يبدأ بـ https://script.google.com وينتهي بـ /exec');
    return;
  }
  props_().setProperty('BASE_URL', url);
  ui.alert('تم حفظ الرابط. شغّل الآن «② تجهيز الروابط وأزرار واتساب».');
}

function waNumber_(mobile) { return /^05\d{8}$/.test(mobile) ? '966' + mobile.slice(1) : ''; }

function langFor_(data, chosen) {
  const c = String(chosen || '').trim().toLowerCase();
  if (Object.prototype.hasOwnProperty.call(CONFIG.langs, c)) return c;
  return CONFIG.natLang[data.nationality] || 'ar';
}

function linkFor_(base, token, lang) {
  return base + (base.indexOf('?') >= 0 ? '&' : '?') + 't=' + token + (lang !== 'ar' ? '&lang=' + lang : '');
}

function waFormula_(mobile, lang, name, link) {
  const num = waNumber_(mobile);
  if (!num) return '';
  const msg = CONFIG.waMessage[lang].replace('{name}', name).replace('{link}', link);
  return '=HYPERLINK("https://wa.me/' + num + '?text=' + encodeURIComponent(msg).replace(/"/g, '%22') + '","إرسال واتساب")';
}

// the rep sheet read once: {t, byNo: {empNo: rowValues}}
function repIndex_() {
  const t = table_(SHEET_REP);
  const byNo = {};
  if (t.lastRow >= 2) {
    const ec = col_(t, EMP_NO_HEADER);
    t.sheet.getRange(2, 1, t.lastRow - 1, t.lastCol).getValues().forEach(function (r) {
      const n = cellText_(r[ec]);
      if (n) byNo[n] = r;
    });
  }
  return {t: t, byNo: byNo};
}

// {empNo, data, photos, isRep} from an employees-sheet row (+ its rep row, if any)
function record_(t, row, ri) {
  const empNo = cellText_(row[col_(t, EMP_NO_HEADER)]);
  const data = {};
  FIELDS_PLAIN_.forEach(function (f) { const c = fieldCol_(t, f); if (c !== undefined) data[f.key] = cellText_(row[c]); });
  const photos = {};
  const rr = ri.byNo[empNo];
  const isRep = !!rr || cellText_(row[sysCol_(t, 'isRep')]) === 'نعم';
  if (rr) {
    FIELDS_REP_.forEach(function (f) {
      const c = fieldCol_(ri.t, f);
      if (c === undefined) return;
      const v = cellText_(rr[c]);
      if (f.kind === 'photo') { if (v) photos[f.key] = v; } else data[f.key] = v;
    });
  }
  return {empNo: empNo, data: data, photos: photos, isRep: isRep, missing: LG.missing(data, photos, isRep)};
}

function prepareLinks() {
  const ui = adminUi_();
  const base = baseUrl_();
  if (!base) {
    ui.alert('انشر التطبيق أولًا (نشر > نشر جديد > تطبيق ويب) ثم اختر «ضبط رابط النشر» والصق الرابط.');
    return;
  }
  withLock_(function () {
    const t = table_(SHEET_EMP);
    if (t.lastRow < 2) { ui.alert('لا توجد بيانات في ورقة «' + SHEET_EMP + '».'); return; }
    const ri = repIndex_();
    const rows = t.sheet.getRange(2, 1, t.lastRow - 1, t.lastCol).getValues();
    const idx = {};
    SYS.forEach(function (p) { idx[p[0]] = sysCol_(t, p[0]); });
    const first = Math.min.apply(null, SYS.map(function (p) { return idx[p[0]]; }));
    const last = Math.max.apply(null, SYS.map(function (p) { return idx[p[0]]; }));
    const mobileCol = fieldCol_(t, LG.BY_KEY.mobile);
    const seen = {}, seenTok = {};
    let made = 0, dup = 0;
    const sysBlock = [], waCells = [];
    rows.forEach(function (r) {
      const empNo = cellText_(r[col_(t, EMP_NO_HEADER)]);
      if (!empNo) { sysBlock.push(r.slice(first, last + 1).map(cellText_)); waCells.push(['']); return; }
      if (seen[empNo]) {
        dup++;
        const c = r.slice(first, last + 1).map(cellText_);
        c[idx.note - first] = 'رقم وظيفي مكرر: لن يُنشأ له رابط';
        c[idx.token - first] = ''; c[idx.link - first] = ''; c[idx.wa - first] = '';
        sysBlock.push(c); waCells.push(['']); return;
      }
      seen[empNo] = true;
      const rec = record_(t, r, ri);
      // a token must be 64 hex chars and unique: anything else (an empty cell, a stray paste, a copied row) gets a fresh one
      const tok = cellText_(r[idx.token]);
      if (!/^[0-9a-f]{64}$/.test(tok) || seenTok[tok]) { r[idx.token] = newToken_(); made++; }
      seenTok[cellText_(r[idx.token])] = true;
      if (!cellText_(r[idx.status])) r[idx.status] = ST.UNOPENED;
      if (ri.byNo[empNo]) r[idx.isRep] = 'نعم';
      const lang = langFor_(rec.data, r[idx.lang]);
      const link = linkFor_(base, cellText_(r[idx.token]), lang);
      r[idx.link] = link;
      r[idx.missing] = String(rec.missing.length);
      const c = r.slice(first, last + 1).map(cellText_);
      c[idx.wa - first] = '';
      sysBlock.push(c);
      waCells.push([waFormula_(cellText_(r[mobileCol]), lang, LG.displayName(rec.data, empNo), link)]);
    });
    const block = t.sheet.getRange(2, first + 1, rows.length, last - first + 1);
    block.setNumberFormat('@');
    block.setValues(sysBlock);
    const wa = t.sheet.getRange(2, idx.wa + 1, rows.length, 1);
    wa.setNumberFormat('General');
    wa.setFormulas(waCells);
    ss_().toast('روابط جديدة: ' + made + (dup ? ' | أرقام مكررة: ' + dup : ''), 'تم', 8);
  });
}

function recomputeAll() {
  const ui = adminUi_();
  withLock_(function () {
    const t = table_(SHEET_EMP);
    if (t.lastRow < 2) return;
    const ri = repIndex_();
    const mc = sysCol_(t, 'missing');
    const rows = t.sheet.getRange(2, 1, t.lastRow - 1, t.lastCol).getValues();
    const out = rows.map(function (r) {
      return [cellText_(r[col_(t, EMP_NO_HEADER)]) ? String(record_(t, r, ri).missing.length) : ''];
    });
    const rng = t.sheet.getRange(2, mc + 1, out.length, 1);
    rng.setNumberFormat('@');
    rng.setValues(out);
  });
  ui.alert('تم تحديث عدد الحقول الناقصة لكل موظف.');
}

function buildAlerts() {
  const ui = adminUi_();
  const r = ui.prompt('تنبيهات الانتهاء', 'خلال كم يومًا؟ (مثال: 60)', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  const days = Math.max(1, parseInt(r.getResponseText(), 10) || 60);
  const t = table_(SHEET_EMP);
  const ri = repIndex_();
  const now = new Date();
  const todayMs = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const found = [];
  if (t.lastRow >= 2) {
    t.sheet.getRange(2, 1, t.lastRow - 1, t.lastCol).getValues().forEach(function (row) {
      const rec = record_(t, row, ri);
      if (!rec.empNo || rec.data.employment_status === 'منتهية خدمته') return;
      CONFIG.expiryKeys.forEach(function (k) {
        const f = LG.BY_KEY[k[0]];
        if (f.repOnly && !rec.isRep) return;
        const ms = LG.parseDate(rec.data[k[0]] || '');
        if (ms === null) return;
        const left = Math.round((ms - todayMs) / 86400000);
        if (left <= days) found.push([rec.empNo, LG.displayName(rec.data, rec.empNo), k[1], LG.iso(ms), left]);
      });
    });
  }
  found.sort(function (a, b) { return a[4] - b[4]; });
  const ss = ss_();
  let sh = ss.getSheetByName(SHEET_ALERTS);
  if (!sh) sh = ss.insertSheet(SHEET_ALERTS);
  sh.clear();
  sh.setRightToLeft(true);
  const all = [['الرقم الوظيفي', 'الاسم', 'الوثيقة', 'تاريخ الانتهاء', 'المتبقي (يوم)']].concat(found.map(function (r) { return r.map(String); }));
  ensureGrid_(sh, all.length, 5);
  sh.getRange(1, 1, all.length, 5).setNumberFormat('@').setValues(all);
  sh.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#1f3a5f').setFontColor('#ffffff');
  ui.alert('وُجدت ' + found.length + ' وثيقة منتهية أو تنتهي خلال ' + days + ' يومًا. انظر ورقة «' + SHEET_ALERTS + '».');
}

function regenLinkForRow() {
  const ui = adminUi_();
  const sh = ss_().getActiveSheet();
  if (sh.getName() !== SHEET_EMP) { ui.alert('اختر خلية داخل صف الموظف في ورقة «' + SHEET_EMP + '».'); return; }
  const row = sh.getActiveRange().getRow();
  if (row < 2) return;
  if (ui.alert('سيتوقف رابط هذا الموظف الحالي عن العمل. متابعة؟', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const t = table_(SHEET_EMP);
  const tokenCell = sh.getRange(row, sysCol_(t, 'token') + 1);
  tokenCell.setNumberFormat('@');
  tokenCell.setValue(newToken_());
  ui.alert('تم. شغّل الآن «② تجهيز الروابط» لتحديث الرابط وزر واتساب لهذا الموظف.');
}

function backupNow() {
  const ui = adminUi_();
  const ss = ss_();
  const rootId = props_().getProperty('PHOTO_FOLDER_ID');
  const parent = rootId ? DriveApp.getFolderById(rootId) : DriveApp.getRootFolder();
  const copy = DriveApp.getFileById(ss.getId()).makeCopy('نسخة احتياطية ' + stamp_(), parent);
  ui.alert('تم إنشاء نسخة: ' + copy.getName() + '\nالنسخة تحتوي بيانات شخصية. أبقِها في مكان محمي.');
}

// Approval guard (simple trigger): only a complete record can be approved; returning needs a note.
function onEdit(e) {
  try {
    if (!e || !e.range || e.range.getNumRows() !== 1 || e.range.getNumColumns() !== 1) return;
    const sh = e.range.getSheet();
    if (sh.getName() !== SHEET_EMP || e.range.getRow() < 2) return;
    const t = table_(SHEET_EMP);
    if (e.range.getColumn() - 1 !== sysCol_(t, 'status')) return;
    const rowValues = sh.getRange(e.range.getRow(), 1, 1, t.lastCol).getValues()[0];
    const revert = function (msg) { e.range.setValue(e.oldValue || ''); e.source.toast(msg, 'لم يتم التغيير', 8); };
    if (e.value === ST.APPROVED) {
      const m = record_(t, rowValues, repIndex_()).missing;
      if (m.length > 0) revert('لا يمكن الاعتماد: ينقص ' + m.length + ' حقل مطلوب.');
    } else if (e.value === ST.RETURNED) {
      if (!cellText_(rowValues[sysCol_(t, 'note')])) revert('اكتب ملاحظة المراجعة أولًا ثم اختر «معاد للتعديل».');
    }
  } catch (err) { console.error(err); }
}
