// Local stand-in for Google: serves Index.html and routes google.script.run calls to Code.gs running on the mocks.
// Used only for browser tests:  node apps_script/test/serve.js [port]
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const {Env} = require('./mocks');
const {makeLogic_} = require('../src/logic.js');

const PORT = Number(process.argv[2] || 8765);
const CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
const LG = makeLogic_(CONFIG);
const BASE = `http://127.0.0.1:${PORT}/exec`;
const env = new Env({url: BASE});
env.sandbox().setupSheets();

const norm = (h) => String(h).replace(/\*/g, '').replace(/\s+/g, ' ').trim();
function col(sheet, header) {
  for (let c = 1; c <= sheet.maxCols; c++) { const x = sheet.cells['1:' + c]; if (x && norm(x.v) === norm(header)) return c; }
  throw new Error(header);
}
function paste(sheetName, row, data, empNo) {
  const sh = env.ss.getSheetByName(sheetName);
  const put = (h, v) => { const c = col(sh, h); sh.cells[row + ':' + c] = {v, fmt: '@'}; };
  put('الرقم الوظيفي', empNo);
  Object.keys(data).forEach((k) => put(LG.BY_KEY[k].xlsx, data[k]));
}
const BASE_PERSON = {name_en: 'Md Rahim', nationality: 'بنغلاديشي', gender: 'ذكر', birth_date: '1992-03-04', id_type: 'إقامة',
  id_number: '2123456789', id_expiry: '2027-01-01', mobile: '0511111111', city: 'الرياض', emergency_name: 'Karim',
  emergency_relation: 'أخ/أخت', emergency_phone: '+8801712345678', job_title: 'مندوب توصيل', department: 'العمليات',
  work_location: 'الرياض', manager_emp_no: '1001', start_date: '2023-02-01', employment_status: 'على رأس العمل'};
paste('الموظفون', 2, BASE_PERSON, '2001');
paste('المناديب', 2, {rep_code: 'R-21', region: 'الرياض', supervisor_emp_no: '1001'}, '2001');
paste('الموظفون', 3, Object.assign({}, BASE_PERSON, {name_en: 'Ravi Kumar', nationality: 'هندي', id_number: '2111111111', mobile: '0522222222'}), '2002');
env.sandbox().prepareLinks();

function tokenOf(empNo) {
  const sh = env.ss.getSheetByName('الموظفون');
  for (let r = 2; r < 10; r++) { const c = sh.cells[r + ':' + col(sh, 'الرقم الوظيفي')]; if (c && c.v === empNo) return sh.cells[r + ':' + col(sh, 'الرمز السري')].v; }
}

const SHIM = `<script>
window.google = {script: {run: new Proxy({}, {get(_, name) {
  return null;
}})}};
(function () {
  function makeRun(ok, bad) {
    return new Proxy({}, {get(_, name) {
      if (name === 'withSuccessHandler') return (f) => makeRun(f, bad);
      if (name === 'withFailureHandler') return (f) => makeRun(ok, f);
      return (...args) => {
        fetch('/rpc/' + name, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(args)})
          .then((r) => r.json()).then((j) => { if (j.error) { if (bad) bad(new Error(j.error)); } else if (ok) ok(j.result); },
                                      (e) => { if (bad) bad(e); });
      };
    }});
  }
  window.google.script.run = makeRun(null, null);
})();
</script>`;

http.createServer((req, res) => {
  const url = new URL(req.url, BASE);
  if (req.method === 'GET' && url.pathname === '/exec') {
    env.mode = 'web';
    const out = env.sandbox().doGet({parameter: Object.fromEntries(url.searchParams)});
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
    return res.end(out.html.replace('<head>', '<head>' + SHIM));
  }
  if (req.method === 'POST' && url.pathname.startsWith('/rpc/')) {
    let body = '';
    req.on('data', (d) => { body += d; });
    req.on('end', () => {
      const name = decodeURIComponent(url.pathname.slice(5));
      res.writeHead(200, {'Content-Type': 'application/json'});
      try {
        env.mode = 'web';   // everything coming from a web page runs outside the Sheet UI
        const sb = env.sandbox();
        if (name.endsWith('_') || typeof sb[name] !== 'function') throw new Error('Script function not found: ' + name);
        const r = sb[name](...JSON.parse(body || '[]'));
        res.end(JSON.stringify({result: r === undefined ? null : r}));
      } catch (e) { res.end(JSON.stringify({error: String(e.message || e)})); }
    });
    return;
  }
  if (url.pathname === '/__state') {
    const sh = env.ss.getSheetByName('الموظفون');
    const rep = env.ss.getSheetByName('المناديب');
    const row = (s, r) => { const o = {}; for (let c = 1; c <= s.maxCols; c++) { const h = s.cells['1:' + c]; if (h) o[norm(h.v)] = (s.cells[r + ':' + c] || {v: ''}).v; } return o; };
    const files = Object.values(env.files).filter((f) => !f.trashed).map((f) => ({name: f.name, size: f.bytes.length, b64: Buffer.from(f.bytes.map((b) => b & 255)).toString('base64')}));
    res.writeHead(200, {'Content-Type': 'application/json'});
    return res.end(JSON.stringify({emp1: row(sh, 2), emp2: row(sh, 3), rep1: row(rep, 2), files}));
  }
  res.writeHead(404); res.end('not found');
}).listen(PORT, '127.0.0.1', () => {
  console.log(JSON.stringify({ready: true, base: BASE, rep: tokenOf('2001'), staff: tokenOf('2002')}));
});
