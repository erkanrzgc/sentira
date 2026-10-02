const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../experiments/review_screen');
const appSource = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const modelSource = fs.readFileSync(path.join(root, 'model.js'), 'utf8');
const scaffoldIds = ['review-data', 'progress', 'page-count', 'previous', 'next', 'source-image',
  'fields', 'error', 'digest', 'zoom', 'zoom-value', 'download-decisions', 'timer',
  'start-timer', 'pause-timer', 'download-timer'];

// Static contract for this template's quoted attributes, not HTML parsing.
function assertScaffoldIds(template) {
  const ids = [...template.matchAll(/\sid\s*=\s*(["'])(.*?)\1/g)].map(match => match[2]);
  for (const id of scaffoldIds) assert.equal(ids.filter(value => value === id).length, 1,
    `Expected exactly one scaffold ID: ${id}`);
}
test('saved template contains each unit scaffold ID exactly once', () => {
  const template = fs.readFileSync(path.join(root, 'screen.html'), 'utf8');
  assertScaffoldIds(template);
  assert.throws(() => assertScaffoldIds(template.replace('id="fields"', 'id="removed-fields"')),
    {code: 'ERR_ASSERTION'});
  assert.throws(() => assertScaffoldIds(template + '<div id="fields"></div>'),
    {code: 'ERR_ASSERTION'});
});

// Explicit unit double only: no HTML parser, browser, layout, bubbling, focus,
// native select behaviour or actual downloads. Dispatch calls registered listeners.
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.listeners = new Map();
    this.style = {}; this.value = ''; this.textContent = ''; this.disabled = false;
  }
  addEventListener(name, fn) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(fn);
  }
  dispatch(name, event = {}) { for (const fn of this.listeners.get(name) || []) fn(event); }
  append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  remove() { this.parent.children = this.parent.children.filter(child => child !== this); }
  click() { if (!this.disabled) this.dispatch('click'); }
}
function fixture() {
  const field = (id, page_id, extra = {}) => ({id, page_id, image: page_id,
    field: 'Synthetic field', candidate: 'Synthetic candidate', candidate_status: 'found', engine_status: 'ok', ...extra});
  return {packet_sha256: 'a'.repeat(64), images: {one: 'synthetic-one', two: 'synthetic-two'},
    packet: {fields: [field('one:value', 'one'), field('two:missing', 'two', {candidate: null, candidate_status: 'missing'}),
      field('two:failed', 'two', {engine_status: 'failed'})]}};
}
function mount(source = appSource) {
  const document = new Element(), window = new Element(), downloads = [], blobs = new Map();
  document.body = new Element('body'); document.hidden = false;
  for (const id of scaffoldIds) {
    const element = new Element(); element.id = id; document.body.append(element);
  }
  document.getElementById = id => {
    function find(node) { if (node.id === id) return node; for (const child of node.children) { const result = find(child); if (result) return result; } }
    return find(document.body);
  };
  document.createElement = tag => {
    const element = new Element(tag);
    if (tag === 'a') element.addEventListener('click', () => downloads.push({name: element.download, blob: blobs.get(element.href)}));
    return element;
  };
  document.getElementById('review-data').textContent = JSON.stringify(fixture());
  let now = 0;
  const intervals = [], timeouts = [];
  const context = vm.createContext({document, window, Blob, performance: {now: () => now},
    URL: {createObjectURL(blob) { const url = `unit-blob:${blobs.size}`; blobs.set(url, blob); return url; }, revokeObjectURL(url) { blobs.delete(url); }},
    setInterval(fn) { intervals.push(fn); }, setTimeout(fn) { timeouts.push(fn); }});
  vm.runInContext(modelSource, context, {filename: 'model.js'});
  vm.runInContext(source, context, {filename: 'app.js'});
  const get = id => { const element = document.getElementById(id); assert.ok(element, `Missing control ${id}`); return element; };
  return {document, window, downloads, get, click: id => get(id).click(),
    edit(id, value) { const element = get(id); assert.equal(element.disabled, false); element.value = value; element.dispatch(element.tag === 'select' ? 'change' : 'input'); },
    time(value) { now = value; for (const fn of intervals) fn(); },
    visible(value) { document.hidden = !value; document.dispatch('visibilitychange'); }};
}
function navigationScenario(source = appSource) {
  const app = mount(source);
  app.edit('action-0', 'correct'); app.edit('value-0', 'Corrected synthetic value'); app.edit('reason-0', 'Synthetic transcription mismatch');
  app.click('next'); assert.match(app.get('page-count').textContent, /Page 2 \/ 2/);
  app.edit('action-1', 'withhold'); app.edit('reason-1', 'Unreadable synthetic source');
  app.click('previous');
  assert.equal(app.get('action-0').value, 'correct');
  assert.equal(app.get('value-0').value, 'Corrected synthetic value');
  assert.equal(app.get('reason-0').value, 'Synthetic transcription mismatch');
  app.click('next'); assert.equal(app.get('reason-1').value, 'Unreadable synthetic source');
  return app;
}
test('application events retain corrections and reasons across two synthetic pages', () => { navigationScenario(); });
test('pending reversion omits draft and a valid withhold downloads a decision blob', async () => {
  const app = navigationScenario(); app.click('previous'); app.edit('action-0', 'pending'); app.click('download-decisions');
  assert.equal(app.downloads.length, 1); const download = app.downloads[0];
  assert.equal(download.name, 'decisions.toml'); assert.equal(download.blob.type, 'application/toml');
  const content = await download.blob.text();
  assert.match(content, /packet_sha256 = "a{64}"/);
  assert.match(content, /field_id = "two:missing"\naction = "withhold"\nreason = "Unreadable synthetic source"/);
  assert.doesNotMatch(content, /one:value|two:failed|Corrected synthetic value/);
});
test('missing candidates and failed OCR disable their accept options', () => {
  const app = mount();
  assert.equal(app.get('action-0').children.find(option => option.value === 'accept').disabled, false);
  app.click('next');
  for (const id of ['action-1', 'action-2']) assert.equal(app.get(id).children.find(option => option.value === 'accept').disabled, true);
});
test('an invalid draft on another page blocks all decision downloads until repaired', () => {
  const app = mount(); app.edit('action-0', 'correct'); app.edit('value-0', 'Replacement');
  app.click('next'); app.edit('action-1', 'withhold'); app.edit('reason-1', 'Unreadable');
  app.click('download-decisions'); assert.equal(app.downloads.length, 0); assert.match(app.get('error').textContent, /nonempty/);
  app.click('previous'); app.edit('reason-0', 'Synthetic mismatch'); app.click('download-decisions');
  assert.equal(app.downloads.length, 1); assert.equal(app.get('error').textContent, '');
});
function visibilityScenario(source = appSource) {
  const app = mount(source); app.time(100); app.click('start-timer'); app.time(300); app.visible(false);
  app.time(900); app.visible(true); app.time(1200);
  assert.equal(app.get('timer').textContent, '200 ms (paused)');
  return app;
}
test('visibility events pause elapsed time and require a manual restart', async () => {
  const app = visibilityScenario(); app.visible(false); app.click('start-timer'); app.time(1300);
  assert.equal(app.get('timer').textContent, '200 ms (paused)');
  app.visible(true); app.click('start-timer'); app.time(1500); app.click('pause-timer'); app.time(2000);
  app.click('download-timer');
  const record = JSON.parse(await app.downloads[0].blob.text());
  assert.equal(record.active_visible_ms, 400); assert.equal(record.packet_sha256, fixture().packet_sha256);
  assert.equal(record.authenticated_human_review, false); assert.equal(record.measurement, 'browser_session_time');
});
test('beforeunload warns after an edit but leaves an untouched session alone', () => {
  const app = mount();
  function attempt() { const event = {prevented: false, preventDefault() { this.prevented = true; }}; app.window.dispatch('beforeunload', event); return event; }
  assert.equal(attempt().prevented, false);
  app.edit('action-0', 'accept'); const event = attempt();
  assert.equal(event.prevented, true); assert.equal(event.returnValue, '');
});
test('unit scenarios detect in-memory navigation and visibility regressions', () => {
  const navigationMutant = appSource.replace('decisions.get(field.id)', 'undefined');
  const visibilityMutant = appSource.replace("'visibilitychange'", "'unused-visibility-event'");
  assert.notEqual(navigationMutant, appSource); assert.notEqual(visibilityMutant, appSource);
  assert.throws(() => navigationScenario(navigationMutant), {code: 'ERR_ASSERTION'});
  assert.throws(() => visibilityScenario(visibilityMutant), {code: 'ERR_ASSERTION'});
});
test('a successful download clears the unload warning until the next edit', () => {
  const app = mount();
  function attempt() { const event = {prevented: false, preventDefault() { this.prevented = true; }}; app.window.dispatch('beforeunload', event); return event; }
  app.edit('action-0', 'accept'); app.click('download-decisions');
  assert.equal(app.downloads.length, 1); assert.equal(attempt().prevented, false);
  app.edit('action-0', 'pending'); assert.equal(attempt().prevented, true);
});
test('a valid download clears a stale error message', () => {
  const app = mount(); app.edit('action-0', 'accept');
  app.get('error').textContent = 'Stale validation message';
  app.click('download-decisions');
  assert.equal(app.downloads.length, 1); assert.equal(app.get('error').textContent, '');
});
test('pagehide pauses a running timer', () => {
  const app = mount(); app.time(100); app.click('start-timer'); app.time(400);
  app.window.dispatch('pagehide'); app.time(900);
  assert.equal(app.get('timer').textContent, '300 ms (paused)');
  const mutant = mount(appSource.replace("'pagehide'", "'unused-pagehide-event'"));
  mutant.time(100); mutant.click('start-timer'); mutant.time(400); mutant.window.dispatch('pagehide'); mutant.time(900);
  assert.notEqual(mutant.get('timer').textContent, '300 ms (paused)');
});
