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
  pipeline: {release:'4.2',scoring_ready:true,granite_ready:false,
    scoring_blockers:[],granite_blockers:['Test model unavailable'],tables:[]},
  workspace: {id: 'CERT r4.2 preview', mode: 'activity', day: '2010-01-02',
    cases: Array.from({length:54}, (_,i) => ({person:`ACT-${String(i+1).padStart(3,'0')}`,
      rank:i+1,score:null,status:'Not inferred',strength:'Not scored',facts:[],cited:[],problems:[]})),
    metrics: {employees: 54, events: 54, note: 'Test preview'}, warnings: []},
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
assert.match(element('nav').innerHTML, /href="#setup"/);
assert.doesNotMatch(element('#main').innerHTML, /Generate new detector scores/);
context.location.hash = '#alerts';
vm.runInContext('route()', context);
let previewHtml = element('#main').innerHTML;
assert.ok(previewHtml.indexOf('aria-label="Selected employee"') < previewHtml.indexOf('<h2>54 employees</h2>'));
assert.ok(previewHtml.indexOf('aria-label="Selected employee"') < previewHtml.indexOf('<table>'));
employeeButtons[10].onclick();
assert.equal(vm.runInContext('selected', context), 'ACT-011');
previewHtml = element('#main').innerHTML;
assert.match(previewHtml.slice(previewHtml.indexOf('aria-label="Selected employee"'),previewHtml.indexOf('</section>')), /ACT-011/);
assert.ok(previewHtml.indexOf('aria-label="Selected employee"') < previewHtml.indexOf('<h2>54 employees</h2>'));
const navigationRequests = requests.length;
context.location.hash = '#setup';
vm.runInContext('route()', context);
assert.equal(vm.runInContext('page', context), 'setup');
assert.match(element('#main').innerHTML, /Generate new detector scores/);
assert.match(element('#main').innerHTML, /Test model unavailable/);
assert.match(element('nav').innerHTML, /href="#setup" class="active" aria-current="page"/);
assert.equal(requests.length, navigationRequests, 'Opening setup must not start analysis or make a new data request');
context.location.hash = '#overview';
vm.runInContext('route()', context);
assert.doesNotMatch(element('#main').innerHTML, /Generate new detector scores/);

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
const sampleRequests = requests.length;
element('#refresh').onclick();
assert.equal(requests.length, sampleRequests);
assert.match(element('#main').innerHTML, /Sample data is static; no files were reloaded/);
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
assert.doesNotMatch(element('#main').innerHTML, /Test model unavailable|Generate new detector scores|Optional commands for a new run/);
assert.doesNotMatch(element('#main').innerHTML, /GRANITE UNAVAILABLE|SCORES UNAVAILABLE/);
context.location.hash = '#setup';
vm.runInContext('route()', context);
assert.match(element('#main').innerHTML, /Saved runner results loaded/);
assert.match(element('#main').innerHTML, /1 saved detector score/);
assert.match(element('#main').innerHTML, /Viewing these results does not require a configured model/);
assert.match(element('#main').innerHTML, /Test model unavailable/);
assert.match(element('#main').innerHTML, /<details class="panel pipeline" open/);
assert.doesNotMatch(element('#main').innerHTML, /Highest-ranked detector scores/);
context.location.hash = '#overview';
vm.runInContext('route()', context);
employeeButtons[0].onclick();
assert.equal(context.location.hash, '#detail/U-0001');
assert.match(element('#main').innerHTML, /Saved Granite response validated/);
vm.runInContext("remote.workspace.cases[0].status='Fallback';render()", context);
assert.match(element('#main').innerHTML, /Showing the deterministic evidence-based fallback/);
vm.runInContext("remote.workspace.cases[0].status='Not inferred';render()", context);
assert.match(element('#main').innerHTML, /No saved Granite response is available/);
vm.runInContext(`remote.workspace.cases.push({person:'U-0002',rank:2,score:4.5,
  strength:'weak',status:'Not inferred',facts:[],cited:[],problems:[]});
  page='alerts';selected='U-0002';render()`, context);
const savedData = vm.runInContext('JSON.parse(JSON.stringify(remote))', context);
assert.match(element('#main').innerHTML, /1 saved run available to this dashboard/);
element('#refresh').onclick();
assert.match(element('#main').innerHTML, /Refreshing saved data/);
assert.match(element('#main').innerHTML, /id="refresh" disabled aria-busy="true"/);
assert.match(requests[0].url, /run=synthetic-test/);
assert.match(requests[0].url, /attempt=attempt-1/);
element('#refresh').onclick();
assert.equal(requests.length, 1, 'Refresh must not enqueue duplicate pending requests');
await reply(requests.shift(), savedData);
assert.match(element('#main').innerHTML, /Refreshed at .*No changes in saved data/);
assert.equal(vm.runInContext('selected', context), 'U-0002');
assert.doesNotMatch(element('#main').innerHTML, /id="refresh" disabled/);

element('#refresh').onclick();
const updatedData = JSON.parse(JSON.stringify(savedData));
updatedData.runs.push({id:'synthetic-next-day',day:'2010-08-03'});
updatedData.workspace.cases[0].score = 8.125;
await reply(requests.shift(), updatedData);
assert.match(element('#main').innerHTML, /Saved data updated/);
assert.match(element('#main').innerHTML, /2 saved runs available to this dashboard/);
assert.match(element('#main').innerHTML, /2010-08-03/);
assert.match(element('#main').innerHTML, /8.125/);
assert.equal(vm.runInContext('selected', context), 'U-0002');

element('#refresh').onclick();
requests.shift().resolve({ok:false,json:async()=>({error:'Temporary read error'})});
await new Promise(resolve => setTimeout(resolve, 0));
assert.match(element('#main').innerHTML, /role="alert"/);
assert.match(element('#main').innerHTML, /Refresh failed: Temporary read error/);
assert.match(element('#main').innerHTML, /Previously loaded results are still displayed/);
assert.match(element('#main').innerHTML, /8.125/);
assert.doesNotMatch(element('#main').innerHTML, /id="refresh" disabled/);

element('#attempt').onchange({target: {value: 'attempt-1'}});
assert.match(requests[0].url, /attempt=attempt-1/);
await reply(requests.shift(), empty);
console.log('UI tests passed: System setup tab, activity selection placement, proxy paths, employee actions, saved results, refresh feedback and failures, and attempt selection.');
