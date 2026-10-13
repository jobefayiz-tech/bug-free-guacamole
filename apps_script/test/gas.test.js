'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {Env} = require('./mocks');
const {makeLogic_} = require('../src/logic.js');

const CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
const VEC = JSON.parse(fs.readFileSync(path.join(__dirname, 'vectors.json'), 'utf8'));
const LG = makeLogic_(CONFIG);
const BASE = 'https://script.google.com/macros/s/AKfycbxTEST/exec';

// ---------------------------------------------------------------- helpers
function norm(h) { return String(h).replace(/\*/g, '').replace(/\s+/g, ' ').trim(); }

function colOf(sheet, header) {
  for (let c = 1; c <= sheet.maxCols; c++) {
    const cell = sheet.cells['1:' + c];
    if (cell && norm(cell.v) === norm(header)) return c;
  }
  throw new Error('no column ' + header);
}

// simulate HR pasting a row from Excel: values keep their type (strings, numbers, Date objects)
function paste(env, sheetName, row, byKey, empNo) {
  const sh = env.ss.getSheetByName(sheetName);
  const put = (header, v) => { const c = colOf(sh, header); sh.cells[row + ':' + c] = {v, fmt: (sh.cells[row + ':' + c] || {fmt: '@'}).fmt}; };
  put('الرقم الوظيفي', empNo);
  Object.keys(byKey).forEach((k) => put(LG.BY_KEY[k].xlsx, byKey[k]));
}

function cell(env, sheetName, row, header) {
  const sh = env.ss.getSheetByName(sheetName);
  const c = sh.cells[row + ':' + colOf(sh, header)];
  return c ? c.v : '';
}

const PERSON = {name_ar: 'أحمد محمد', name_en: 'Ahmed Mohammed', nationality: 'مصري', gender: 'ذكر', birth_date: '1990-05-01',
  id_type: 'هوية وطنية', id_number: '1234567890', id_expiry: '2030-01-01', mobile: '0512345678', city: 'الرياض',
  emergency_name: 'خالد', emergency_relation: 'أخ/أخت', emergency_phone: '0555555555', job_title: 'محاسب', department: 'المالية',
  work_location: 'الرياض', manager_emp_no: 'E1', start_date: '2020-01-01', employment_status: 'على رأس العمل'};

function newEnv() {
  const env = new Env({url: BASE});
  env.sandbox().setupSheets();
  return env;
}

function setupWith(people) {   // people: [[empNo, data, repData?]]
  const env = newEnv();
  let r = 2, rr = 2;
  people.forEach(([no, data, rep]) => {
    paste(env, 'الموظفون', r++, Object.assign({}, PERSON, data), no);
    if (rep) paste(env, 'المناديب', rr++, rep, no);
  });
  env.sandbox().prepareLinks();
  return env;
}

function tokenOf(env, empNo) {
  const sh = env.ss.getSheetByName('الموظفون');
  for (let r = 2; r < 100; r++) {
    const c = sh.cells[r + ':' + colOf(sh, 'الرقم الوظيفي')];
    if (c && String(c.v) === empNo) return String(sh.cells[r + ':' + colOf(sh, 'الرمز السري')].v);
  }
  throw new Error('no ' + empNo);
}
function rowOf(env, empNo) {
  const sh = env.ss.getSheetByName('الموظفون');
  for (let r = 2; r < 100; r++) { const c = sh.cells[r + ':' + colOf(sh, 'الرقم الوظيفي')]; if (c && String(c.v) === empNo) return r; }
}

function login(env, empNo, last4) {
  const tok = tokenOf(env, empNo);
  const v = env.call('apiVerify', tok, last4 || PERSON.id_number.slice(-4));
  assert.equal(v.ok, true, JSON.stringify(v));
  return {tok, ses: v.session};
}

const FORM = {name_ar: 'أحمد محمد', name_en: 'Ahmed Mohammed', nationality: 'مصري', gender: 'ذكر', birth_date: '1990-05-01',
  id_type: 'هوية وطنية', id_number: '1234567890', id_expiry: '2030-01-01', mobile: '٠٥١٢٣٤٥٦٧٨', city: 'الرياض',
  emergency_name: 'خالد', emergency_relation: 'أخ/أخت', emergency_phone: '+91 98765 43210', consent: true};

// a tiny but valid-enough JPEG (only the header is inspected by the server)
const JPEG_B64 = Buffer.from([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0xFF, 0xD9]).toString('base64');

// ---------------------------------------------------------------- parity with the Python implementation
test('validation parity with Python: clean()', () => {
  let n = 0;
  VEC.clean.forEach((v) => {
    const got = LG.clean(LG.BY_KEY[v.key], v.raw, VEC.today);
    assert.deepEqual(got, [v.value, v.error], `${v.key} <- ${JSON.stringify(v.raw)}`);
    n++;
  });
  assert.ok(n > 300);
});

test('validation parity with Python: missing() and displayName()', () => {
  VEC.missing.forEach((v) => {
    const got = LG.missing(v.data, v.photos, v.isRep, v.owner || undefined);
    assert.deepEqual(got, v.missing, JSON.stringify(v));
  });
  VEC.names.forEach((v) => assert.equal(LG.displayName(v.data, v.fallback), v.name));
});

// ---------------------------------------------------------------- HR setup
test('setupSheets builds both sheets with the template headers and enough grid', () => {
  const env = newEnv();
  const emp = env.ss.getSheetByName('الموظفون');
  const rep = env.ss.getSheetByName('المناديب');
  assert.ok(emp && rep && env.ss.getSheetByName('لوحة المتابعة'));
  assert.ok(emp.maxRows >= 2001 && emp.maxCols >= 31 + 12);
  const headers = [];
  for (let c = 1; c <= 43; c++) headers.push(norm(emp.cells['1:' + c].v));
  CONFIG.fields.filter((f) => !f.repOnly).forEach((f) => assert.ok(headers.includes(norm(f.xlsx)), f.xlsx));
  ['الرمز السري', 'الحالة', 'ملاحظة المراجعة', 'رابط الموظف', 'إرسال واتساب'].forEach((h) => assert.ok(headers.includes(h), h));
  CONFIG.fields.filter((f) => f.repOnly).forEach((f) => assert.ok(colOf(rep, f.xlsx) > 0));
  assert.equal(emp.rtl, true);
  assert.ok(env.menus.length === 0);   // menu is built by onOpen
  env.sandbox().onOpen();
  assert.equal(env.menus[0].items.length, 7);
  env.menus[0].items.forEach(([, fn]) => assert.equal(typeof env.sandbox()[fn], 'function', fn));
});

test('dashboard: labels are text and only the count column holds formulas (no #NAME?/#ERROR!)', () => {
  const env = newEnv();
  const dash = env.ss.getSheetByName('لوحة المتابعة');
  const cells = Object.keys(dash.cells).map((k) => dash.cells[k]);
  assert.ok(cells.length >= 20);
  assert.deepEqual(cells.filter((c) => c.error || /^#/.test(String(c.v))), []);
  assert.equal(dash.cells['1:1'].v, 'المؤشر');
  assert.equal(dash.cells['1:2'].v, 'العدد');
  assert.equal(dash.cells['3:1'].v, 'لم يفتح');
  for (let r = 2; r <= 10; r++) {
    assert.ok(!dash.cells[r + ':1'].formula, 'label row ' + r);
    assert.match(dash.cells[r + ':2'].formula, /^=/, 'formula row ' + r);
  }
});

test('setupSheets is idempotent and keeps existing data', () => {
  const env = setupWith([['E1', {}]]);
  env.sandbox().setupSheets();
  assert.equal(String(cell(env, 'الموظفون', 2, 'الاسم الكامل (إنجليزي)')), 'Ahmed Mohammed');
});

test('prepareLinks: unique long tokens, language by nationality, WhatsApp link, rep flag, duplicates', () => {
  const env = setupWith([
    ['E1', {nationality: 'بنغلاديشي', name_en: 'Rahim', id_number: '1111111111'}],
    ['E2', {nationality: 'باكستاني', name_en: 'Imran', id_number: '1222222222', mobile: '0577777777'}],
    ['E3', {nationality: 'مصري', id_number: '1333333333', mobile: '0588888888'}, {rep_code: 'R-3', region: 'الرياض', supervisor_emp_no: 'E1'}],
    ['E3', {nationality: 'مصري'}],   // duplicate employee number
  ]);
  const t = ['E1', 'E2', 'E3'].map((n) => tokenOf(env, n));
  assert.equal(new Set(t).size, 3);
  t.forEach((x) => assert.match(x, /^[0-9a-f]{64}$/));
  assert.ok(cell(env, 'الموظفون', 2, 'رابط الموظف').endsWith(`?t=${t[0]}&lang=bn`));
  assert.ok(cell(env, 'الموظفون', 3, 'رابط الموظف').endsWith(`?t=${t[1]}&lang=ur`));
  assert.ok(cell(env, 'الموظفون', 4, 'رابط الموظف').endsWith(`?t=${t[2]}`));
  const wa = env.ss.getSheetByName('الموظفون').cells['3:' + colOf(env.ss.getSheetByName('الموظفون'), 'إرسال واتساب')];
  assert.match(wa.url, /^https:\/\/wa\.me\/966577777777\?text=/);
  assert.ok(decodeURIComponent(wa.url).includes(t[1]));
  assert.equal(cell(env, 'الموظفون', 4, 'مندوب؟'), 'نعم');
  assert.equal(cell(env, 'الموظفون', 5, 'الرمز السري'), '');
  assert.match(cell(env, 'الموظفون', 5, 'ملاحظة المراجعة'), /مكرر/);
  // running again keeps the same tokens
  env.sandbox().prepareLinks();
  assert.deepEqual(['E1', 'E2', 'E3'].map((n) => tokenOf(env, n)), t);
});

test('prepareLinks asks to deploy first when there is no URL', () => {
  const env = new Env({url: ''});
  env.sandbox().setupSheets();
  env.sandbox().prepareLinks();
  assert.match(env.alerts.pop(), /انشر التطبيق/);
});

test('setBaseUrl validates the URL', () => {
  const env = newEnv();
  env.prompts.push('https://evil.example/exec');
  env.sandbox().setBaseUrl();
  assert.match(env.alerts.pop(), /غير صحيح/);
  env.prompts.push(BASE);
  env.sandbox().setBaseUrl();
  assert.equal(env.props.BASE_URL, BASE);
});

test('admin functions refuse to run outside the Sheet UI (web page visitors)', () => {
  const env = setupWith([['E1', {}]]);
  env.mode = 'web';
  ['setupSheets', 'prepareLinks', 'setBaseUrl', 'recomputeAll', 'buildAlerts', 'regenLinkForRow', 'backupNow', 'onOpen'].forEach((fn) => {
    assert.throws(() => env.sandbox()[fn](), /getUi/, fn);
  });
});

// ---------------------------------------------------------------- employee API
test('apiStart / apiVerify: bad token, wrong digits, lockout, success', () => {
  const env = setupWith([['E1', {}]]);
  const tok = tokenOf(env, 'E1');
  assert.deepEqual(env.call('apiStart', 'x'.repeat(64)), {ok: false, error: 'bad_link'});
  assert.deepEqual(env.call('apiStart', ''), {ok: false, error: 'bad_link'});
  assert.deepEqual(env.call('apiStart', {}), {ok: false, error: 'bad_link'});
  const s = env.call('apiStart', tok);
  assert.equal(s.ok, true); assert.equal(s.needVerify, true); assert.equal(s.name, 'أحمد محمد'); assert.equal(s.session, undefined);
  for (let i = 0; i < 4; i++) assert.deepEqual(env.call('apiVerify', tok, '0000'), {ok: false, error: 'mismatch'});
  assert.deepEqual(env.call('apiVerify', tok, '0000'), {ok: false, error: 'locked'});
  assert.deepEqual(env.call('apiVerify', tok, '7890'), {ok: false, error: 'locked'});     // even the right digits are refused
  assert.equal(env.call('apiStart', tok).locked, true);
});

test('apiVerify accepts Arabic-Indic digits and returns a session', () => {
  const env = setupWith([['E1', {}]]);
  const r = env.call('apiVerify', tokenOf(env, 'E1'), '٧٨٩٠');
  assert.equal(r.ok, true); assert.match(r.session, /^[0-9a-f]{64}$/);
});

test('a record with no ID on file is protected by the secret link alone', () => {
  const env = setupWith([['E9', {id_number: ''}]]);
  const s = env.call('apiStart', tokenOf(env, 'E9'));
  assert.equal(s.needVerify, false); assert.ok(s.session);
});

test('apiLoad needs a valid session for THIS employee', () => {
  const env = setupWith([['E1', {}], ['E2', {id_number: '1222222222', mobile: '0577777777'}]]);
  const a = login(env, 'E1');
  const b = login(env, 'E2', '2222');
  assert.deepEqual(env.call('apiLoad', a.tok, 'nope'), {ok: false, error: 'session'});
  assert.deepEqual(env.call('apiLoad', a.tok, b.ses), {ok: false, error: 'session'});     // someone else's session
  const r = env.call('apiLoad', a.tok, a.ses);
  assert.equal(r.ok, true); assert.equal(r.empNo, 'E1'); assert.equal(r.data.city, 'الرياض');
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'قيد التعبئة');
  assert.ok(cell(env, 'الموظفون', 2, 'فُتح في'));
});

test('draft save keeps valid fields, rejects bad ones, and preserves leading zeros / ISO dates as text', () => {
  const env = setupWith([['E1', {mobile: '0500000000'}]]);
  const {tok, ses} = login(env, 'E1');
  const r = env.call('apiSave', tok, ses, Object.assign({}, FORM, {mobile: '12', city: 'جدة', id_expiry: '2031-02-03'}), 'draft');
  assert.equal(r.ok, true); assert.equal(r.saved, false); assert.ok(r.errors.mobile);
  assert.equal(cell(env, 'الموظفون', 2, 'المدينة'), 'جدة');
  assert.equal(cell(env, 'الموظفون', 2, 'رقم الجوال (05xxxxxxxx)'), '0500000000');    // rejected value not stored
  assert.equal(cell(env, 'الموظفون', 2, 'تاريخ انتهاء الهوية / الإقامة'), '2031-02-03'); // stays a string, not a Date
  const ok = env.call('apiSave', tok, ses, FORM, 'draft');
  assert.equal(ok.saved, true);
  assert.strictEqual(cell(env, 'الموظفون', 2, 'رقم الجوال (05xxxxxxxx)'), '0512345678');  // string with the leading zero
  assert.strictEqual(cell(env, 'الموظفون', 2, 'جوال الطوارئ'), '+919876543210');
});

test('submit: blocked when something is missing, then goes to review; consent time recorded', () => {
  const env = setupWith([['E1', {}]]);
  const {tok, ses} = login(env, 'E1');
  let r = env.call('apiSave', tok, ses, Object.assign({}, FORM, {consent: false}), 'submit');
  assert.equal(r.submitted, false); assert.equal(r.errors.consent, 'هذا الحقل مطلوب');
  assert.notEqual(cell(env, 'الموظفون', 2, 'الحالة'), 'بانتظار المراجعة');
  r = env.call('apiSave', tok, ses, FORM, 'submit');
  assert.equal(r.submitted, true); assert.equal(r.status, 'بانتظار المراجعة');
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'بانتظار المراجعة');
  assert.ok(cell(env, 'الموظفون', 2, 'وقت الموافقة')); assert.ok(cell(env, 'الموظفون', 2, 'أُرسل في'));
  assert.equal(cell(env, 'الموظفون', 2, 'حقول ناقصة'), '0');
});

test('the WhatsApp HYPERLINK formula survives employee saves', () => {
  const env = setupWith([['E1', {}]]);
  const {tok, ses} = login(env, 'E1');
  env.call('apiSave', tok, ses, FORM, 'draft');
  const sh = env.ss.getSheetByName('الموظفون');
  const c = sh.cells['2:' + colOf(sh, 'إرسال واتساب')];
  assert.ok(c.formula && c.url.startsWith('https://wa.me/'));
});

test('employee cannot change HR-owned fields, status or the token by posting extra values', () => {
  const env = setupWith([['E1', {}]]);
  const {tok, ses} = login(env, 'E1');
  env.call('apiSave', tok, ses, Object.assign({}, FORM, {job_title: 'مدير عام', department: 'الإدارة', status: 'معتمد', token: 'x', employment_status: 'في إجازة'}), 'submit');
  assert.equal(cell(env, 'الموظفون', 2, 'المسمى الوظيفي'), 'محاسب');
  assert.equal(cell(env, 'الموظفون', 2, 'المسمى الوظيفي') === 'مدير عام', false);
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'بانتظار المراجعة');
  assert.equal(tokenOf(env, 'E1'), tok);
});

test('profession on Iqama is required only for residents', () => {
  const env = setupWith([['B1', {id_type: 'إقامة', id_number: '2123456789', nationality: 'بنغلاديشي'}]]);
  const {tok, ses} = login(env, 'B1', '6789');
  let r = env.call('apiSave', tok, ses, Object.assign({}, FORM, {id_type: 'إقامة', id_number: '2123456789'}), 'submit');
  assert.equal(r.errors.iqama_profession, 'هذا الحقل مطلوب');
  r = env.call('apiSave', tok, ses, Object.assign({}, FORM, {id_type: 'إقامة', id_number: '2123456789', iqama_profession: 'Delivery driver'}), 'submit');
  assert.equal(r.submitted, true);
});

test('after review: HR approval guard, return with note, employee re-edit goes back to review', () => {
  const env = setupWith([['E1', {}]]);
  const {tok, ses} = login(env, 'E1');
  env.call('apiSave', tok, ses, FORM, 'submit');
  const sh = env.ss.getSheetByName('الموظفون');
  const statusCol = colOf(sh, 'الحالة');
  const edit = (value, old) => {
    sh.cells['2:' + statusCol] = {v: value, fmt: '@'};
    const range = sh.getRange(2, statusCol, 1, 1);
    env.sandbox().onEdit({range, value, oldValue: old, source: env.ss});
  };
  // returning without a note is reverted
  edit('معاد للتعديل', 'بانتظار المراجعة');
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'بانتظار المراجعة');
  sh.cells['2:' + colOf(sh, 'ملاحظة المراجعة')] = {v: 'صحح العنوان', fmt: '@'};
  edit('معاد للتعديل', 'بانتظار المراجعة');
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'معاد للتعديل');
  assert.equal(env.call('apiLoad', tok, ses).note, 'صحح العنوان');
  // approving while the record is incomplete is reverted (job_title removed by HR)
  sh.cells['2:' + colOf(sh, 'المسمى الوظيفي')] = {v: '', fmt: '@'};
  edit('معتمد', 'معاد للتعديل');
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'معاد للتعديل');
  assert.ok(env.ss.toasts.some((t) => /لا يمكن الاعتماد/.test(t.msg)));
  sh.cells['2:' + colOf(sh, 'المسمى الوظيفي')] = {v: 'محاسب', fmt: '@'};
  env.call('apiSave', tok, ses, FORM, 'submit');
  edit('معتمد', 'بانتظار المراجعة');
  assert.equal(cell(env, 'الموظفون', 2, 'الحالة'), 'معتمد');
  // employee edits an approved record: it goes back to review; an invalid edit makes it a draft
  let r = env.call('apiSave', tok, ses, Object.assign({}, FORM, {city: 'الدمام'}), 'draft');
  assert.equal(r.status, 'بانتظار المراجعة');
  r = env.call('apiSave', tok, ses, Object.assign({}, FORM, {mobile: '1'}), 'submit');
  assert.equal(r.status, 'قيد التعبئة');
});

// ---------------------------------------------------------------- reps and photos
const REP = {rep_code: 'R-1', region: 'الرياض', supervisor_emp_no: 'E9'};
const REP_FORM = Object.assign({}, FORM, {app_name: 'نينجا', app_id: '445566', location_consent: 'نعم', vehicle_type: 'سيارة شخصية',
  license_no: '1020304050', license_expiry: '2029-05-05', plate_no: 'ح ك م 4821', registration_expiry: '2027-05-05'});

test('rep: needs the five photos when there is a vehicle; photos stored in Drive and linked in the sheet', () => {
  const env = setupWith([['R1', {}, REP]]);
  const {tok, ses} = login(env, 'R1');
  let r = env.call('apiSave', tok, ses, REP_FORM, 'submit');
  assert.equal(r.submitted, false);
  ['photo_front', 'photo_back', 'photo_right', 'photo_left', 'photo_odometer'].forEach((k) => assert.equal(r.errors[k], 'هذا الحقل مطلوب', k));
  CONFIG.photoKeys.forEach((k) => {
    const p = env.call('apiPhoto', tok, ses, k, JPEG_B64);
    assert.equal(p.ok, true, JSON.stringify(p));
  });
  const folder = env.rootFolder; // photos live under the root photo folder created in setup
  const all = Object.values(env.files).filter((f) => !f.trashed);
  assert.equal(all.length, 5);
  const url = cell(env, 'المناديب', 2, 'صورة العداد (رابط أو اسم الملف)');
  assert.match(url, /^https:\/\/drive\.google\.com\/file\/d\//);
  r = env.call('apiSave', tok, ses, REP_FORM, 'submit');
  assert.equal(r.submitted, true, JSON.stringify(r.errors));
  assert.equal(cell(env, 'المناديب', 2, 'رقم الأيدي (ID) في التطبيق'), '445566');
  assert.strictEqual(cell(env, 'المناديب', 2, 'رقم اللوحة'), 'ح ك م 4821');
  assert.equal(cell(env, 'الموظفون', 2, 'حقول ناقصة'), '0');
  assert.ok(folder);
});

test('rep: no vehicle means photos are not required; unknown app is rejected', () => {
  const env = setupWith([['R1', {}, REP]]);
  const {tok, ses} = login(env, 'R1');
  let r = env.call('apiSave', tok, ses, Object.assign({}, REP_FORM, {vehicle_type: 'بدون مركبة', app_name: 'أوبر'}), 'submit');
  assert.equal(r.errors.app_name, 'اختر من القائمة');
  r = env.call('apiSave', tok, ses, Object.assign({}, REP_FORM, {vehicle_type: 'بدون مركبة'}), 'submit');
  assert.equal(r.submitted, true);
});

test('photo upload: rejects non-JPEG, bad base64, oversize, wrong key, non-reps; replaces old file', () => {
  const env = setupWith([['R1', {}, REP], ['E2', {id_number: '1222222222', mobile: '0577777777'}]]);
  const {tok, ses} = login(env, 'R1');
  assert.equal(env.call('apiPhoto', tok, ses, 'photo_front', Buffer.from('<script>alert(1)</script>').toString('base64')).error, 'bad_image');
  assert.equal(env.call('apiPhoto', tok, ses, 'photo_front', '!!!not base64!!!').error, 'bad_image');
  assert.equal(env.call('apiPhoto', tok, ses, 'photo_front', 'A'.repeat(7 * 1024 * 1024)).error, 'too_big');
  assert.equal(env.call('apiPhoto', tok, ses, '../../etc/passwd', JPEG_B64).error, 'bad_request');
  assert.equal(env.call('apiPhoto', tok, ses, 'name_ar', JPEG_B64).error, 'bad_request');
  assert.equal(env.call('apiPhoto', tok, 'bad-session', 'photo_front', JPEG_B64).error, 'session');
  const e2 = login(env, 'E2', '2222');
  assert.equal(env.call('apiPhoto', e2.tok, e2.ses, 'photo_front', JPEG_B64).error, 'bad_request');
  env.call('apiPhoto', tok, ses, 'photo_front', JPEG_B64);
  env.call('apiPhoto', tok, ses, 'photo_front', JPEG_B64);
  const live = Object.values(env.files).filter((f) => !f.trashed && f.name === 'photo_front.jpg');
  assert.equal(live.length, 1);
});

test('photos of two employees go to separate folders named after the (sanitized) employee number', () => {
  const env = setupWith([['R1', {}, REP], ['R/2', {id_number: '1222222222', mobile: '0577777777'}, REP]]);
  const a = login(env, 'R1');
  const b = login(env, 'R/2', '2222');
  env.call('apiPhoto', a.tok, a.ses, 'photo_front', JPEG_B64);
  env.call('apiPhoto', b.tok, b.ses, 'photo_front', JPEG_B64);
  const root = env.folders[env.props.PHOTO_FOLDER_ID];
  assert.deepEqual(root.folders.map((f) => f.name).sort(), ['R1', 'R_2']);
});

// ---------------------------------------------------------------- misc
test('dates pasted from Excel (Date objects, numbers) are handled', () => {
  const env = setupWith([['E1', {id_expiry: new Date(2020, 0, 1), id_number: 1234567890}]]);
  const {tok, ses} = login(env, 'E1');
  assert.equal(env.call('apiLoad', tok, ses).data.id_expiry, '2020-01-01');
});

test('buildAlerts lists expired and soon-to-expire documents, skips ended employment', () => {
  const env = setupWith([['E1', {id_expiry: '2020-01-01'}], ['E2', {id_expiry: '2099-01-01', id_number: '1222222222', mobile: '0577777777'}],
    ['E3', {id_expiry: '2020-01-01', employment_status: 'منتهية خدمته', id_number: '1333333333', mobile: '0588888888'}]]);
  env.prompts.push('60');
  env.sandbox().buildAlerts();
  const sh = env.ss.getSheetByName('تنبيهات الانتهاء');
  assert.equal(sh.cells['2:1'].v, 'E1');
  assert.equal(sh.cells['3:1'], undefined);
  assert.ok(Number(sh.cells['2:5'].v) < 0);
});

test('recomputeAll fills the missing-fields counter', () => {
  const env = setupWith([['E1', {job_title: ''}]]);
  env.sandbox().recomputeAll();
  assert.equal(cell(env, 'الموظفون', 2, 'حقول ناقصة'), '2');   // job title (emptied) + the employee's own consent
});

test('doGet renders the page and escapes the token inside the page data', () => {
  const env = setupWith([['E1', {}]]);
  const out = env.sandbox().doGet({parameter: {t: '</script><script>alert(1)</script>', lang: 'bn'}});
  assert.equal(out.title, 'بياناتي الوظيفية');
  assert.ok(!out.html.includes('<script>alert(1)'));
  assert.ok(out.html.includes('\\u003c/script\\u003e'));
  const boot = /var BOOT = (\{.*\});/.exec(out.html);
  assert.ok(boot);
  assert.equal(JSON.parse(boot[1]).lang, 'bn');
});

test('regenLinkForRow replaces the token (old link stops working)', () => {
  const env = setupWith([['E1', {}]]);
  const old = tokenOf(env, 'E1');
  const sh = env.ss.getSheetByName('الموظفون');
  sh.active = sh.getRange(2, 1, 1, 1);
  env.ss.active = sh;
  env.sandbox().regenLinkForRow();
  assert.notEqual(tokenOf(env, 'E1'), old);
  assert.deepEqual(env.call('apiStart', old), {ok: false, error: 'bad_link'});
});

test('backupNow copies the spreadsheet into Drive', () => {
  const env = setupWith([['E1', {}]]);
  env.sandbox().backupNow();
  assert.match(env.alerts.pop(), /نسخة احتياطية/);
});

test('text typed by an employee can never become a spreadsheet formula', () => {
  const env = setupWith([['E1', {}]]);
  const {tok, ses} = login(env, 'E1');
  env.call('apiSave', tok, ses, Object.assign({}, FORM, {name_en: '=IMPORTXML("http://evil","//a")', city: '=1+1'}), 'draft');
  const sh = env.ss.getSheetByName('الموظفون');
  ['الاسم الكامل (إنجليزي)', 'المدينة'].forEach((h) => {
    const c = sh.cells['2:' + colOf(sh, h)];
    assert.equal(c.formula, undefined);
    assert.ok(String(c.v).startsWith(' ='), h);
  });
});

test('junk tokens are rejected before any sheet is read', () => {
  const env = setupWith([['E1', {}]]);
  let reads = 0;
  const sh = env.ss.getSheetByName('الموظفون');
  const orig = sh.getRange.bind(sh);
  sh.getRange = (...a) => { reads++; return orig(...a); };
  ['', 'abc', 'x'.repeat(64), 'A'.repeat(64), '0'.repeat(63), null, undefined, 123, [], {}].forEach((t) => {
    assert.deepEqual(env.call('apiStart', t), {ok: false, error: 'bad_link'});
  });
  assert.equal(reads, 0);
});
