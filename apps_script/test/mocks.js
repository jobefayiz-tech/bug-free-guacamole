// Minimal in-memory imitation of the Google services used by Code.gs, good enough to run the real code.
// It is deliberately strict where Google is strict (grid bounds) and imitates Sheets' auto-conversion
// of "05123..." / "2030-01-01" in cells that are NOT formatted as plain text, so formatting bugs show up.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');

function coerce(value, fmt) {
  if (fmt === '@') return value === null || value === undefined ? '' : String(value);
  if (typeof value === 'string') {
    if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  return value;
}

class Range {
  constructor(sheet, r, c, nr, nc) {
    if (r < 1 || c < 1 || nr < 1 || nc < 1) throw new Error('Range coordinates must be positive');
    if (r + nr - 1 > sheet.maxRows || c + nc - 1 > sheet.maxCols) {
      throw new Error('The coordinates or dimensions of the range are invalid (outside the sheet grid ' +
        sheet.maxRows + 'x' + sheet.maxCols + ')');
    }
    Object.assign(this, {sheet, r, c, nr, nc});
  }
  cell(i, j) { return this.sheet.cells[(this.r + i) + ':' + (this.c + j)] || {v: '', fmt: 'General'}; }
  getRow() { return this.r; }
  getColumn() { return this.c; }
  getNumRows() { return this.nr; }
  getNumColumns() { return this.nc; }
  getSheet() { return this.sheet; }
  getValues() {
    const out = [];
    for (let i = 0; i < this.nr; i++) {
      const row = [];
      for (let j = 0; j < this.nc; j++) {
        const cell = this.cell(i, j);
        row.push(cell.formula ? cell.display : cell.v);
      }
      out.push(row);
    }
    return out;
  }
  getValue() { return this.getValues()[0][0]; }
  setValues(vals) {
    if (vals.length !== this.nr || vals.some((r) => r.length !== this.nc)) throw new Error('Number of rows/columns mismatch: setValues');
    for (let i = 0; i < this.nr; i++) {
      for (let j = 0; j < this.nc; j++) {
        const k = (this.r + i) + ':' + (this.c + j);
        const old = this.sheet.cells[k] || {fmt: 'General'};
        this.sheet.cells[k] = {v: coerce(vals[i][j], old.fmt), fmt: old.fmt};
      }
    }
    return this;
  }
  setValue(v) {
    const k = this.r + ':' + this.c;
    const old = this.sheet.cells[k] || {fmt: 'General'};
    this.sheet.cells[k] = {v: coerce(v, old.fmt), fmt: old.fmt};
    return this;
  }
  setFormulas(f) {
    for (let i = 0; i < this.nr; i++) {
      for (let j = 0; j < this.nc; j++) {
        const text = f[i][j];
        const k = (this.r + i) + ':' + (this.c + j);
        const old = this.sheet.cells[k] || {fmt: 'General'};
        if (typeof text === 'string' && text.charAt(0) === '=') {
          const m = /^=HYPERLINK\("([^"]*)","([^"]*)"\)$/.exec(text);
          this.sheet.cells[k] = {v: '', fmt: old.fmt, formula: text, display: m ? m[2] : '', url: m ? m[1] : ''};
        } else {
          this.sheet.cells[k] = {v: text, fmt: old.fmt};
        }
      }
    }
    return this;
  }
  setNumberFormat(fmt) {
    for (let i = 0; i < this.nr; i++) {
      for (let j = 0; j < this.nc; j++) {
        const k = (this.r + i) + ':' + (this.c + j);
        const cell = this.sheet.cells[k] || {v: '', fmt: 'General'};
        cell.fmt = fmt;
        this.sheet.cells[k] = cell;
      }
    }
    return this;
  }
  setDataValidation(rule) { this.sheet.validations.push({range: this, rule}); return this; }
  protect() { return this; }
}
['setHorizontalAlignment', 'setFontWeight', 'setBackground', 'setFontColor', 'setWrap'].forEach((m) => {
  Range.prototype[m] = function () { return this; };
});

class Sheet {
  constructor(name, id) {
    Object.assign(this, {name, id, cells: {}, maxRows: 1000, maxCols: 26, validations: [], cfRules: [], rtl: false});
  }
  getName() { return this.name; }
  getMaxRows() { return this.maxRows; }
  getMaxColumns() { return this.maxCols; }
  insertRowsAfter(after, n) { this.maxRows += n; }
  insertColumnsAfter(after, n) { this.maxCols += n; }
  getRange(r, c, nr, nc) { return new Range(this, r, c, nr || 1, nc || 1); }
  getLastRow() { let m = 0; Object.keys(this.cells).forEach((k) => { const c = this.cells[k]; if (c.formula || (c.v !== '' && c.v !== null)) m = Math.max(m, +k.split(':')[0]); }); return m; }
  getLastColumn() { let m = 0; Object.keys(this.cells).forEach((k) => { const c = this.cells[k]; if (c.formula || (c.v !== '' && c.v !== null)) m = Math.max(m, +k.split(':')[1]); }); return m; }
  clear() { this.cells = {}; return this; }
  setFrozenRows() {} setFrozenColumns() {} setRowHeight() {} setColumnWidth() {}
  setRightToLeft(v) { this.rtl = v; }
  setConditionalFormatRules(rules) { this.cfRules = rules; }
  getActiveRange() { return this.active || new Range(this, 2, 1, 1, 1); }
}

class Spreadsheet {
  constructor() { this.sheets = []; this.toasts = []; this.active = null; this.id = 'ss-1'; }
  getId() { return this.id; }
  getSheetByName(n) { return this.sheets.find((s) => s.name === n) || null; }
  insertSheet(n) { const s = new Sheet(n, this.sheets.length + 1); this.sheets.push(s); return s; }
  getActiveSheet() { return this.active || this.sheets[0]; }
  toast(msg, title) { this.toasts.push({msg, title}); }
}

function builder() { const store = []; const o = {calls: store}; const p = new Proxy(o, { get(t, k) { if (k === 'build') return () => ({calls: store}); if (k in t) return t[k]; return (...a) => { store.push([k, a]); return p; }; } }); return p; }

class Env {
  constructor(opts = {}) {
    this.ss = new Spreadsheet();
    this.mode = 'sheet';              // 'web' makes getUi() throw like Google does outside the sheet UI
    this.props = {};
    this.cache = {};
    this.files = {};                  // id -> file
    this.folders = {};                // id -> folder
    this.alerts = [];
    this.prompts = [];                // scripted answers for ui.prompt
    this.alertAnswer = 'YES';
    this.menus = [];
    this.url = opts.url || '';
    this.nextId = 1;
    this.indexHtml = fs.readFileSync(path.join(ROOT, 'Index.html'), 'utf8');
    this.codeText = fs.readFileSync(path.join(ROOT, 'Code.gs'), 'utf8');
    this.rootFolder = this.makeFolder('root');
  }
  id(prefix) { return prefix + '-' + (this.nextId++); }
  makeFolder(name) {
    const env = this;
    const f = {id: env.id('folder'), name, folders: [], files: [],
      getId() { return f.id; }, getName() { return f.name; },
      getFoldersByName(n) { const m = f.folders.filter((x) => x.name === n); return iter(m); },
      createFolder(n) { const c = env.makeFolder(n); f.folders.push(c); return c; },
      getFilesByName(n) { return iter(f.files.filter((x) => x.name === n && !x.trashed)); },
      createFile(blob) {
        const file = {id: env.id('file'), name: blob.name, bytes: blob.bytes, trashed: false,
          getUrl() { return 'https://drive.google.com/file/d/' + file.id + '/view'; }, getName() { return file.name; },
          setTrashed(v) { file.trashed = v; return file; }};
        f.files.push(file); env.files[file.id] = file; return file;
      }};
    this.folders[f.id] = f;
    return f;
  }
  // a fresh JS context for every call = a fresh Apps Script execution (services keep their state)
  sandbox() {
    const env = this;
    const ui = {
      ButtonSet: {OK_CANCEL: 'OK_CANCEL', YES_NO: 'YES_NO', OK: 'OK'}, Button: {OK: 'OK', CANCEL: 'CANCEL', YES: 'YES', NO: 'NO'},
      createMenu(name) { const m = {name, items: []}; const b = {addItem(l, fn) { m.items.push([l, fn]); return b; }, addSeparator() { return b; }, addToUi() { env.menus.push(m); }}; return b; },
      alert(msg) { env.alerts.push(msg); return env.alertAnswer; },
      prompt(title, text) { const a = env.prompts.shift(); return {getSelectedButton: () => (a === undefined ? 'CANCEL' : 'OK'), getResponseText: () => a}; },
    };
    const sb = {
      console, Date, Math, JSON, Object, Array, String, Number, RegExp, Error, parseInt, parseFloat, encodeURIComponent, Promise,
      SpreadsheetApp: {
        getActiveSpreadsheet: () => env.ss, openById: () => env.ss,
        getUi() { if (env.mode === 'web') throw new Error('Cannot call SpreadsheetApp.getUi() from this context.'); return ui; },
        newDataValidation: builder, newConditionalFormatRule: builder,
      },
      DriveApp: {
        createFolder: (n) => { const f = env.makeFolder(n); return f; },
        getFolderById: (id) => env.folders[id],
        getRootFolder: () => env.rootFolder,
        getFileById: () => ({makeCopy: (name, folder) => folder.createFile({name, bytes: []})}),
      },
      Utilities: {
        getUuid: () => crypto.randomUUID(),
        base64Decode: (s) => { if (/[^A-Za-z0-9+\/=\s]/.test(s)) throw new Error('Invalid base64'); return Array.from(Buffer.from(s, 'base64')).map((b) => (b > 127 ? b - 256 : b)); },
        newBlob: (bytes, mime, name) => ({bytes, mime, name}),
        formatDate(d, tz, fmt) {
          const t = new Date(d.getTime() + 3 * 3600 * 1000);
          const p = (n) => String(n).padStart(2, '0');
          const date = t.getUTCFullYear() + '-' + p(t.getUTCMonth() + 1) + '-' + p(t.getUTCDate());
          return fmt === 'yyyy-MM-dd' ? date : date + ' ' + p(t.getUTCHours()) + ':' + p(t.getUTCMinutes());
        },
      },
      Session: {getScriptTimeZone: () => 'Asia/Riyadh'},
      PropertiesService: {getScriptProperties: () => ({getProperty: (k) => (k in env.props ? env.props[k] : null), setProperty: (k, v) => { env.props[k] = v; }})},
      CacheService: {getScriptCache: () => ({
        get: (k) => { const e = env.cache[k]; return e && e.exp > Date.now() ? e.v : null; },
        put: (k, v, s) => { env.cache[k] = {v, exp: Date.now() + s * 1000}; },
        remove: (k) => { delete env.cache[k]; },
      })},
      LockService: {getScriptLock: () => ({waitLock() {}, releaseLock() {}})},
      ScriptApp: {getService: () => ({getUrl: () => env.url})},
      HtmlService: {
        XFrameOptionsMode: {ALLOWALL: 'ALLOWALL'},
        createTemplateFromFile(name) {
          if (name !== 'Index') throw new Error('no such file ' + name);
          const t = {boot: ''};
          t.evaluate = () => {
            const out = {html: env.indexHtml.replace('<?!= boot ?>', () => t.boot), title: '', meta: []};
            out.setTitle = (x) => { out.title = x; return out; };
            out.addMetaTag = (a, b) => { out.meta.push([a, b]); return out; };
            out.setXFrameOptionsMode = () => out;
            out.getContent = () => out.html;
            return out;
          };
          return t;
        },
      },
    };
    vm.createContext(sb);
    vm.runInContext(this.codeText, sb, {filename: 'Code.gs'});
    return sb;
  }
  // results are JSON round-tripped, like google.script.run does (also avoids cross-context prototype mismatches)
  call(fn, ...args) { const r = this.sandbox()[fn](...args); return r === undefined ? r : JSON.parse(JSON.stringify(r)); }
}
function iter(arr) { let i = 0; return {hasNext: () => i < arr.length, next: () => arr[i++]}; }

module.exports = {Env, Sheet, Range, coerce};
