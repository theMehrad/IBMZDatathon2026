// Run with: node tests/dashboard_ui.mjs (no packages required).
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../web/dashboard/pipeline.js', import.meta.url), 'utf8') + '\n' +
  await readFile(new URL('../web/dashboard/app.js', import.meta.url), 'utf8');
const elements = new Map();
let employeeButtons = [];
const element = selector => {
  if (!elements.has(selector)) elements.set(selector, {
    innerHTML: '', textContent: '', insertAdjacentHTML(where, html) { this.notice = html; },
  });
  return elements.get(selector);
};
const requests = [];
const context = vm.createContext({
  document: {querySelector: element, querySelectorAll(selector) {
    if (selector !== '.select-row') return [];
    employeeButtons = [...element('#main').innerHTML.matchAll(/<button class="select-row" data-person="([^"]+)"/g)]
      .map(match => ({dataset: {person: match[1]}}));
    return employeeButtons;
  }},
  window: {addEventListener() {}}, location: {hash: ''},
  sessionStorage: {getItem: () => null}, URLSearchParams, setTimeout,
  fetch: url => new Promise(resolve => requests.push({url, resolve})),
});
const empty = {runs: [], workspace: null, activity_dates: []};
const activity = {
  runs: [], activity_dates: ['2010-01-02'],
  workspace: {id: 'CERT r4.2 preview', mode: 'activity', day: '2010-01-02',
    cases: [], metrics: {employees: 0, events: 0, note: 'Test preview'}, warnings: []},
};
async function reply(request, data) {
  request.resolve({ok: true, json: async () => JSON.parse(JSON.stringify(data))});
  await new Promise(resolve => setTimeout(resolve, 0));
}
function choose(value) {
  element('#source').onchange({target: {value}});
}

vm.runInContext(source, context);
assert.equal(new URL(requests[0].url, 'https://example.test/proxy/8000/').pathname, '/proxy/8000/api/workspace');
assert.equal(new URL(requests[0].url, 'https://example.test/user/tam/proxy/8000/').pathname, '/user/tam/proxy/8000/api/workspace');
assert.equal(new URL(requests[0].url, 'http://127.0.0.1:8000/').pathname, '/api/workspace');
await reply(requests.shift(), activity);
assert.equal(vm.runInContext('activity()', context), true);

choose('runner');
assert.match(requests[0].url, /source=runner/);
assert.equal(vm.runInContext('activity()', context), false);
await reply(requests.shift(), empty);
assert.match(element('#main').innerHTML, /No prepared runner outputs found/);
assert.match(element('#main').innerHTML, /value="runner" selected/);

element('#refresh').onclick();
assert.match(requests[0].url, /source=runner/);
const staleRefresh = requests.shift();
choose('activity');
await reply(requests.shift(), activity);
await reply(staleRefresh, empty);
assert.equal(vm.runInContext('activity()', context), true);
assert.ok(vm.runInContext('remote.workspace', context), element('#main').notice);
assert.equal(element('#dataset-name').textContent, 'CERT r4.2 preview');

choose('runner');
const staleRunner = requests.shift();
choose('sample');
await reply(staleRunner, empty);
assert.equal(vm.runInContext('sample', context), true);
assert.match(element('#main').innerHTML, /24,816/);
assert.match(element('#main').innerHTML, /Inspect employee/);
employeeButtons[0].onclick();
assert.equal(context.location.hash, '#detail/Mara%20Voss');
assert.equal(vm.runInContext('page', context), 'detail');
assert.match(element('#main').innerHTML, /312 customer records/);
context.location.hash = '#alerts';
vm.runInContext('route()', context);
employeeButtons[1].onclick();
assert.equal(vm.runInContext('page', context), 'alerts');
assert.equal(vm.runInContext('selected', context), 'Eli Park');
assert.match(element('#main').innerHTML, /data-person="Eli Park" aria-pressed="true">Selected/);
context.location.hash = '#overview';
vm.runInContext('route()', context);
choose('runner');
await reply(requests.shift(), {
  runs: [{id: 'synthetic-test', day: '2010-08-02'}],
  pipeline: {release: '4.2', scoring_ready: false, granite_ready: false,
    scoring_blockers: ['Test tables unavailable'], granite_blockers: ['Test model unavailable'], tables: []},
  workspace: {id: 'synthetic-test', day: '2010-08-02', cases: [{person: 'U-0001',
    rank: 1, score: 7.25, strength: 'strong', status: 'Accepted', facts: [], cited: [], problems: []}],
    metrics: {employees: null, events: null}, attempts: ['attempt-1'], attempt: 'attempt-1',
    progress: {Accepted: 1, Fallback: 0, 'Not inferred': 0},
    model: {name: 'Synthetic test adapter', sha256: 'test-digest', mode: 'chat', structured_output: true}},
});
assert.match(element('#main').innerHTML, /7.25/);
assert.match(element('#main').innerHTML, /1 Accepted/);
assert.match(element('#main').innerHTML, /Synthetic test adapter/);
assert.match(element('#main').innerHTML, /Test model unavailable/);
assert.match(element('#main').innerHTML, /Saved runner results loaded/);
assert.match(element('#main').innerHTML, /1 saved detector score/);
assert.match(element('#main').innerHTML, /Viewing these results does not require a configured model/);
assert.match(element('#main').innerHTML, /Setup for new analysis \(optional\)/);
assert.doesNotMatch(element('#main').innerHTML, /<details class="panel pipeline" open/);
assert.doesNotMatch(element('#main').innerHTML, /GRANITE UNAVAILABLE|SCORES UNAVAILABLE/);
employeeButtons[0].onclick();
assert.equal(context.location.hash, '#detail/U-0001');
assert.match(element('#main').innerHTML, /Saved Granite response validated/);
vm.runInContext("remote.workspace.cases[0].status='Fallback';render()", context);
assert.match(element('#main').innerHTML, /Showing the deterministic evidence-based fallback/);
vm.runInContext("remote.workspace.cases[0].status='Not inferred';render()", context);
assert.match(element('#main').innerHTML, /No saved Granite response is available/);
element('#attempt').onchange({target: {value: 'attempt-1'}});
assert.match(requests[0].url, /attempt=attempt-1/);
await reply(requests.shift(), empty);
console.log('UI tests passed: source switching, proxy paths, employee actions, saved-results status, and attempt selection.');
