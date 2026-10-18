'use strict';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = (name, size=14) => `<img src="assets/img${name}.svg" alt="" width="${size}" height="${size}">`;
const badge = (text, cls='') => `<span class="badge ${cls}">${esc(text)}</span>`;
const num = n => n == null ? '—' : Number(n).toLocaleString(undefined, {maximumFractionDigits:3});
let cursor = -1, dataSource = 'runner', loadVersion = 0;
let loading = false, loadNotice = '', loadError = false;
let remote = {runs:[], workspace:null}, sample = false, selected = null, page = 'overview', query = '', priority = '', review = '';
const sampleNames = ['Mara Voss','Eli Park','Nia Sol','Theo Wren','Aya Reed','Jules Hart'];
const signals = ['After-hours export + upload','Privileged access sequence','Unusual record volume','New external destination','Off-pattern repository access','New device sign-in'];
const sampleFacts = [
  ['F101','21:52:04','Device sign-in','Successful sign-in on managed device NS-042.','auth-0042','LogIn'],
  ['F102','22:03:19','CRM export','312 customer records exported as customers.csv.','crm-0312','FileDown'],
  ['F103','22:11:08','Local archive created','q4-review.zip created on NS-042; size 18 MB.','edr-0018','Archive'],
  ['F104','22:18:42','Browser upload','q4-review.zip, 18 MB, uploaded to transfer.example.','web-0018','Upload']
].map(([id,time,title,text,source,icon]) => ({id,time,title,text,source,icon}));
const demo = {id:'Northstar / demo-01',day:'2026-10-14',release:'Sample',metrics:{employees:128,events:24816,note:'Fictional identities and authored event fixtures.'},warnings:[],cases:sampleNames.map((person,i)=>({person,rank:i+1,score:[94,88,76,71,65,42][i],priority:i<2?'High':i<5?'Medium':'Low',signal:signals[i],employee:['EMP-042 · Finance operations','EMP-017 · Infrastructure','EMP-063 · Customer operations','EMP-091 · Engineering','EMP-028 · People operations','EMP-114 · Sales operations'][i],status:'Sample assessment',facts:i===0?sampleFacts:[],label:i===0?'Potential data movement':'No sample assessment provided',cited:i===0?['F102','F104']:[],strength:'Sample',problems:[]}))};
function activity(){return !sample && (dataSource==='activity'||(dataSource==='auto'&&remote.workspace?.mode==='activity'));}
function workspace(){return sample?demo:remote.workspace;}
function stateKey(c){const w=workspace();return ['outofrole-review',sample?'sample':'runner',w?.id,w?.day,c.person].join(':');}
function reviewState(c){try{return sessionStorage.getItem(stateKey(c)) || (sample && [2,5].includes(c.rank)?'In review':'Unreviewed');}catch{return 'Unreviewed';}}
function current(){const w=workspace();return w?.cases.find(c=>c.person===selected) || w?.cases[0];}
function route(){const parts=location.hash.slice(1).split('/');page=['overview','alerts','detail','setup'].includes(parts[0])?parts[0]:'overview';if(parts[1])selected=decodeURIComponent(parts[1]);cursor=-1;render();const m=$('#main');if(m?.classList){m.classList.remove('enter');void m.offsetWidth;m.classList.add('enter');window.scrollTo?.(0,0);}}
function detailLink(c){return '#detail/'+encodeURIComponent(c.person);}
function panel(title,body,sub=''){return `<section class="panel"><div class="panel-head"><h2>${title}</h2><small>${esc(sub)}</small></div>${body}</section>`;}
function heading(title,subtitle,actions){return `<div class="heading"><div class="eyebrow">${page==='setup'?'WORKSPACE / SYSTEM SETUP':page==='detail'?'DAILY ALERTS / EMPLOYEE DETAIL':'WORKSPACE / '+(page==='alerts'?'DAILY ALERTS':'OVERVIEW')}</div><div class="title-row"><h1>${esc(title)}</h1><div class="actions">${actions}</div></div><p>${esc(subtitle)}</p></div>`;}
function controls(w){return `<div class="panel toolbar"><small>DATASET</small>${icon('Database')}<select id="source" aria-label="Data source"><option value="runner" ${!sample&&!activity()?'selected':''}>Runner outputs</option><option value="sample" ${sample?'selected':''}>Northstar / demo-01 (sample)</option></select>${badge(sample?'SYNTHETIC':activity()?'CERT BENCHMARK / PREVIEW':'PROCESSED / LOCAL')}<div class="date"><small>DAILY WINDOW</small>${icon('CalendarDays')}<select id="run" aria-label="Run and daily window" ${sample||(!activity()&&!remote.runs.length)?'disabled':''}>${activity()?(remote.activity_dates||[]).map(day=>`<option value="${day}" ${w?.day===day?'selected':''}>${day}</option>`).join(''):sample?'<option>14 Oct 2026</option>':remote.runs.length?remote.runs.map(r=>`<option value="${esc(r.id)}" ${w?.id===r.id?'selected':''}>${esc(r.day)} · ${esc(r.id)}</option>`).join(''):'<option>No prepared runs</option>'}</select><small>${activity()?'SOURCE TIME':'UTC'}</small></div><button id="refresh" ${loading?'disabled aria-busy="true"':''}>${loading?'Refreshing…':'Refresh'}</button></div>`;}
function rows(cases){const max=Math.max(1,...workspace().cases.map(c=>c.score??0));return `<div class="scroll"><table><thead><tr>${[activity()?'Row':'Rank','Employee / '+(sample?'fictional':'pseudonym'),'Detection signal','Score','Priority','Fact ID','Granite','Review'].map(t=>`<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${cases.map(c=>`<tr class="row" data-href="${detailLink(c)}"><td class="mono">${String(c.rank).padStart(2,'0')}</td><td><a href="${detailLink(c)}"><strong>${esc(c.person)} ↗</strong></a><p>${esc(c.employee||'Release-local pseudonym')}</p></td><td>${esc(c.signal||'Accumulated unusual activity')}<p class="mono">${esc(workspace().day)} · ${sample?'sample alert':'daily replay'}</p></td><td class="score" title="${esc(c.score)}">${num(c.score)}${c.score==null?'':`<div class="track mini"><i style="width:${c.score/max*100}%"></i></div>`}</td><td>${badge(c.priority||'Unassigned',(c.priority||'').toLowerCase())}</td><td><a href="${detailLink(c)}">${esc(c.facts.map(f=>f.id).join(', ')||'—')}</a></td><td>${badge(c.status||'Not inferred')}</td><td>${badge(reviewState(c),'rv-'+reviewState(c).replace(' ',''))}</td></tr>`).join('')||'<tr><td colspan="8"><div class="empty">No alerts match these filters. <button data-clear>Clear filters</button></div></td></tr>'}</tbody></table></div>`;}
function topSignals(w){const top=w.cases.slice(0,5),max=Math.max(1,...top.map(c=>c.score??0));return `<ol class="signals">${top.map(c=>`<li><span class="mono">${String(c.rank).padStart(2,'0')}</span><a href="${detailLink(c)}"><strong>${esc(c.person)}</strong><small>${esc(c.signal||'Accumulated unusual activity')}</small></a><div class="track"><i style="width:${(c.score??0)/max*100}%"></i></div><span class="mono">${num(c.score)}</span></li>`).join('')||'<li>No alerts loaded.</li>'}</ol>`;}
function overview(w){const counts=['High','Medium','Low'].map(p=>w.cases.filter(c=>c.priority===p).length);let series=sample?[3,4,2,5,4,3,6]:[activity()?w.metrics.events:w.cases.length];return `${guide(w)}<small>${activity()?'ACTIVITY PREVIEW METRICS':'DETECTION METRICS'}</small><div class="metrics">${[['Employees active',w.metrics.employees],[activity()?'Observed logon records':'Processed events',w.metrics.events],[activity()?'Employees in preview':'Ranked alerts',w.cases.length],[sample?'High priority':activity()?'Detector score':'Highest running score',sample?counts[0]:activity()?null:w.cases.length?Math.max(...w.cases.map(c=>c.score??0)):null]].map(([name,value])=>`<section class="panel metric"><p>${name}</p><div class="value">${num(value)}</div></section>`).join('')}</div><div class="two-col">${panel(activity()?'Observed activity':'Daily alert volume',`<div class="chart">${series.map((n,i)=>`<div class="bar">${n}<i style="height:${Math.max(2,n/Math.max(1,...series)*84)}px"></i>${sample?String(i+8).padStart(2,'0')+' OCT':esc(w.day)}</div>`).join('')}</div>`)}${panel('Priority distribution',`<div class="distribution">${sample?['High','Medium','Low'].map((p,i)=>`<label><span>${p}</span><div class="track"><i style="width:${counts[i]/w.cases.length*100}%"></i></div>${counts[i]}</label>`).join(''):'<p>Unassigned for all alerts.</p><p>The runner exports ranks and running scores, without priority thresholds. Scores are not probabilities.</p>'}</div>`)}</div>${panel(activity()?'Employee activity preview':'Top five signals',topSignals(w)+`<div class="foot">Showing ${Math.min(5,w.cases.length)} of ${w.cases.length} ${activity()?'employees':'alerts'}<a href="#alerts">${activity()?'Open employee activity':'Open daily ranked list'} →</a></div>`)}`;}
function queue(w){
  const visible=w.cases.filter(c=>(!priority||(c.priority||'Unassigned')===priority)&&(!review||reviewState(c)===review)&&(!query||[c.person,c.employee,c.signal,...c.facts.map(f=>f.id)].join(' ').toLowerCase().includes(query.toLowerCase())));
  return `<div class="foot"><h2>${w.cases.length} ${activity()?'employees':sample?'sample alerts':'alerts'}</h2><small>${activity()?'Alphabetical employee order · not detector ranks':'Original rank order · scores are not model confidence'}</small></div>${chips(w)}<section class="panel"><div class="filters"><input id="search" type="search" aria-label="Search alerts" placeholder="Search name, employee ID or fact ID" value="${esc(query)}"><select id="priority" aria-label="Filter priority"><option value="">All priorities</option>${(sample?['High','Medium','Low']:['Unassigned']).map(p=>`<option ${priority===p?'selected':''}>${p}</option>`).join('')}</select><select id="review" aria-label="Filter review state"><option value="">All review states</option>${['Unreviewed','In review','Reviewed'].map(p=>`<option ${review===p?'selected':''}>${p}</option>`).join('')}</select><small>${visible.length} OF ${w.cases.length}</small></div>${rows(visible)}<div class="foot">${sample?'All names and signals are fictional.':'Pseudonymized evidence can still contain computer and website identifiers.'}</div></section><p class="tip"><kbd>/</kbd> search · <kbd>j</kbd>/<kbd>k</kbd> move · <kbd>Enter</kbd> open · <kbd>⌘K</kbd> jump to anyone</p>`;
}
function detail(w,c){if(!c)return '<div class="panel empty">This run contains no ranked employees.</div>';return `${stepper(c)}<section class="panel summary"><div><small>${activity()?'PREVIEW ROW':'DAILY RANK'}</small><div class="rank">${String(c.rank).padStart(2,'0')} / ${String(w.cases.length).padStart(2,'0')}</div></div><div class="grow"><h2>${esc(c.signal||'Accumulated unusual activity')}</h2><p class="mono">${esc(w.day)} · ${esc(w.id)}</p></div><div><small>${sample?'SAMPLE SCORE':'RUNNING SCORE'}</small><div class="score">${num(c.score)}${sample?' / 100':''}</div></div><div>${badge(c.priority||'Unassigned',(c.priority||'').toLowerCase())}<p>${esc(reviewState(c))}</p></div></section><div class="two-col"><div>${panel('Activity timeline',`<div class="timeline">${c.facts.length?c.facts.slice().sort((a,b)=>(a.date||a.time||'').localeCompare(b.date||b.time||'')).map(f=>`<div class="event"><small>${esc(f.time||f.date)}</small>${icon(f.icon||'LogIn',13)}<div><strong>${esc(f.title||f.what)}</strong><p>${esc(f.text)}</p><small>${esc(f.source||(activity()?'Observed logon record':'Exported ranked evidence · day precision'))}</small></div><a class="fact-link mono" href="#fact-${esc(f.id)}" data-fact="${esc(f.id)}">[${esc(f.id)}]</a></div>`).join(''):'<div class="note">No evidence facts were exported for this employee. No events have been invented.</div>'}</div>`,sample?'SAMPLE EVENTS · UTC':activity()?'RAW LOGON ACTIVITY · SOURCE TIMESTAMPS':'EXPORTED EVIDENCE · DAY PRECISION')}${panel('Evidence ledger',`<div class="scroll"><table class="register"><thead><tr><th>FACT ID</th><th>SOURCE</th><th>AVAILABLE EVIDENCE</th></tr></thead><tbody>${c.facts.map(f=>`<tr id="fact-${esc(f.id)}"><td>${esc(f.id)}</td><td>${esc(f.source||'packs.json')}</td><td>${esc(f.text)} ${c.cited.includes(f.id)?badge('CITED'):''}</td></tr>`).join('')}</tbody></table></div>`)}</div><div><section class="panel dark"><h2>Granite label</h2><p>${badge(sample?'SAMPLE ASSESSMENT':c.status)}</p><h3>${esc(c.label)}</h3><p>${sample?'Human-authored demonstration label. No model was run.':activity()?'No Granite inference or detector scoring was run for this preview.':c.status==='Accepted'?'Saved Granite response validated against the exported evidence pack.':c.status==='Fallback'?'No Granite response was accepted. Showing the deterministic evidence-based fallback.':'No saved Granite response is available for this employee in the selected attempt.'}</p><hr><p>${sample?'The export and upload occur outside the fixture’s usual hours. This is a review hypothesis, not a determination of intent.':'Evidence strength: '+esc(c.strength)+'. The label does not establish intent or classification accuracy.'}</p><small>CITES ${esc(c.cited.map(id=>'['+id+']').join(' ')||'—')}</small>${c.problems.length?`<p>${esc(c.problems.join('; '))}</p>`:''}</section>${panel('What remains unknown','<div class="note"><p>Business authorization, intent, and full content context are not established by this evidence.</p><p>Do not treat this alert as a confirmed incident.</p></div>')}${panel('Analyst next step','<div class="note">Validate business context and request missing source records before assigning a disposition.</div>')}</div></div>${panel('Cited fact register',`<div class="note"><p>${sample?'Synthetic sample facts only.':'Evidence is scoped to the selected employee and runner day. Pseudonyms are release-local; no answer-key data is displayed.'}</p>${!sample?`<pre>${esc(c.rendered)}</pre>`:''}</div><div class="scroll"><table class="register"><thead><tr><th>FACT ID</th><th>CONTEXT</th><th>VALUE</th></tr></thead><tbody>${[['RUN','Dataset',w.id+' · '+w.day],[activity()?'ROW':'RANK',activity()?'Alphabetical preview':'Daily queue',activity()?c.rank+' · not scored':c.rank+' · running score '+c.score],...c.facts.map(f=>[f.id,'Source evidence',f.text])].map(r=>`<tr>${r.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`)}`;}
function render(){
  const w=workspace(),c=current();selected=c?.person;
  $('#disclosure').innerHTML=activity()?'<strong class="mono">CERT r4.2 / BOUNDED ACTIVITY PREVIEW</strong> | Synthetic benchmark logon records. No detector scores or Granite assessments.':sample?'<strong class="mono">SAMPLE DATA / SYNTHETIC</strong>　 Fictional people, events, metrics and assessments. No real detections or model results.':'<strong class="mono">LOCAL / EXISTING OUTPUTS</strong>　 Read-only data access. No Spark, scoring or inference is started.';
  $('#dataset-name').textContent=w?.id||(activity()?'CERT r4.2 activity':'Runner outputs');
  $('#dataset-date').textContent=w?.day||'No data loaded';
  $('nav').innerHTML=[['overview','Overview','LayoutDashboard'],['alerts',activity()?'Activity preview':'Daily alerts','ListOrdered'],['detail','Employee detail','Fingerprint'],['setup','System setup','Database']].map(([id,name,img])=>`<a href="#${id}" class="${page===id?'active':''}" ${page===id?'aria-current="page"':''}>${icon(img,img==='Database'?14:16)}${name}</a>`).join('');
  const actions=page==='setup'?'<a class="button" href="#overview">← Overview</a>':page==='overview'?`<a class="button primary" href="#alerts">${activity()?'View employee activity':'View daily alerts'} →</a>`:page==='alerts'?`<button id="export">${icon('Download')}Export ${sample?'sample ':''}queue</button>`:`<a class="button" href="#alerts">← ${activity()?'Activity preview':'Daily alerts'}</a>${c?reviewActions(w,c):''}`;
  const title=page==='setup'?'System setup':page==='overview'?'Today’s briefing':page==='alerts'?(activity()?'Employee activity preview.':'The daily review queue.'):c?.person||'Employee detail';
  const subtitle=page==='setup'?'Administrator information for generating new results. Viewing saved scores and assessments does not require a new run.':page==='detail'?(c?.employee||(activity()?'CERT r4.2 identity · observed logon records':'Release-local pseudonym · inspect supporting facts')):sample?'Review the daily signal, then follow the evidence. This workspace contains synthetic scenarios only.':activity()?'Explore existing r4.2 logon records. This bounded preview is not a detector alert queue.':'Review existing detector ranks and checked Granite evidence.';
  let content;
  if(page==='setup'){
    content=pipelinePanel()||panel('System setup',`<div class="note"><p>${sample?'The sample workspace contains authored demonstration data. Choose Runner outputs or CERT r4.2 activity to inspect server readiness.':loading?'Loading server readiness…':'Server readiness is not available yet. Use Refresh to retry.'}</p></div>`);
  }else{
    const warnings=w?(w.warnings||[]).map(t=>`<div class="notice">${esc(t)}</div>`).join(''):'';
    const empty=`<section class="panel empty"><h2>${activity()?'No r4.2 activity loaded':'No prepared runner outputs found'}</h2><p>${activity()?'The activity preview needs an existing logon.csv file in the configured raw-data folder.':'Runner outputs stays selected even when no exports are available. Select System setup for configuration details.'}</p><p>Choose “Northstar / demo-01 (sample)” above to explore the design. Nothing is generated automatically.</p></section>`;
    content=inferencePanel(w)+warnings+(w?(page==='overview'?overview(w):page==='alerts'?queue(w):detail(w,c)):empty);
  }
  $('#main').innerHTML=heading(title,subtitle,actions)+controls(w)+refreshFeedback()+content+`<footer><span>OUTOFROLE / ${sample?'SAMPLE WORKSPACE':'LOCAL WORKSPACE'}</span><span>${esc(w?.day||'')} · ${activity()?'SOURCE TIMESTAMPS':'ALL TIMES UTC'}</span></footer>`;
  bind();bindExtra();
}
function bind(){if($('#attempt'))$('#attempt').onchange=e=>load(workspace().id,undefined,e.target.value); $('#source').onchange=e=>{dataSource=e.target.value;sample=dataSource==='sample';++loadVersion;loading=false;loadNotice='';loadError=false;remote.workspace=null;selected=null;query=priority=review='';render();if(!sample)load();};$('#run').onchange=e=>load(activity()?'activity':e.target.value,activity()?e.target.value:undefined);$('#refresh').onclick=refreshData;for(const id of ['search','priority','review']){const el=$('#'+id);if(el)el.oninput=e=>{const start=e.target.selectionStart;if(id==='search')query=e.target.value;else if(id==='priority')priority=e.target.value;else review=e.target.value;render();if(id==='search'){$('#search').focus();$('#search').setSelectionRange(start,start);}};}for(const [id,value] of [['begin','In review'],['complete','Reviewed']]){const b=$('#'+id);if(b)b.onclick=()=>{try{sessionStorage.setItem(stateKey(current()),value);render();toast(value==='Reviewed'?'Marked reviewed ✓':'Review started');}catch{b.textContent='Session storage unavailable';}};}document.querySelectorAll('[data-fact]').forEach(a=>a.onclick=e=>{e.preventDefault();document.getElementById('fact-'+a.dataset.fact)?.scrollIntoView({behavior:'smooth'});});if($('#export'))$('#export').onclick=()=>{const w=workspace();if(!w)return;const blob=new Blob([JSON.stringify({source:sample?'SAMPLE / SYNTHETIC':activity()?'CERT r4.2 BOUNDED RAW ACTIVITY PREVIEW':'RUNNER OUTPUT',day:w.day,run:w.id,cases:w.cases},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`outofrole-${sample?'sample-':''}${w.day}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};}
function refreshFeedback(){
  const scope = !sample && !activity()
    ? `${remote.runs.length} saved run${remote.runs.length === 1 ? '' : 's'} available to this dashboard. Refresh rereads saved files; it does not create another day.`
    : sample ? 'Sample data is static.' : 'Dates are limited to the bounded activity preview.';
  return `<div class="refresh-feedback"><p id="refresh-status" role="${loadError ? 'alert' : 'status'}" ${loadError ? 'class="error"' : ''}>${esc(loadNotice)}</p><p>${esc(scope)}</p></div>`;
}
function refreshData(){
  if(loading)return;
  if(sample){loadNotice='Sample data is static; no files were reloaded and no analysis was run.';loadError=false;render();return;}
  return load(activity()?'activity':workspace()?.id,activity()?workspace()?.day:undefined,!activity()?workspace()?.attempt:undefined,true);
}
async function load(run,day,attempt,isRefresh=false){
  const version=++loadVersion;
  loading=true;loadError=false;
  loadNotice=isRefresh?'Refreshing saved data…':'Loading saved data…';
  render();
  const params=new URLSearchParams();
  if(dataSource!=='auto')params.set('source',dataSource);
  if(run&&run!=='activity')params.set('run',run);
  if(day)params.set('day',day);
  if(attempt)params.set('attempt',attempt);
  try{
    const response=await fetch('api/workspace'+(params.size?'?'+params.toString():''),{cache:'no-store'});
    const data=await response.json();
    if(version!==loadVersion)return;
    if(!response.ok)throw Error(data.error||'Unable to load outputs');
    const sameRun=remote.workspace?.id===data.workspace?.id;
    const unchanged=JSON.stringify(remote)===JSON.stringify(data);
    remote=data;
    if(dataSource==='auto')dataSource=data.workspace?.mode==='activity'?'activity':'runner';
    if(!sameRun)selected=null;
    loading=false;
    const time=new Date().toLocaleTimeString();
    loadNotice=isRefresh?`Refreshed at ${time}. ${unchanged?'No changes in saved data.':'Saved data updated.'}`:`Loaded at ${time}.`;
    render();
  }catch(e){
    if(version!==loadVersion)return;
    loading=false;loadError=true;
    loadNotice=`${isRefresh?'Refresh':'Load'} failed: ${e.message}. ${remote.workspace?'Previously loaded results are still displayed.':'No new data was loaded.'}`;
    render();
  }
}
window.addEventListener('hashchange',route);route();load();

/* ---- guidance, review flow, shortcuts ---- */
function reviewCounts(w){const r={Unreviewed:0,'In review':0,Reviewed:0};w.cases.forEach(c=>{const k=reviewState(c);r[k]=(r[k]||0)+1;});return r;}
function nextCase(w,after){const cs=w.cases,i=after?cs.indexOf(after)+1:0;return [...cs.slice(i),...cs.slice(0,i)].find(c=>c!==after&&reviewState(c)!=='Reviewed');}
function guide(w){
  if(!w.cases.length)return '';
  const r=reviewCounts(w),n=w.cases.length,next=nextCase(w),pct=Math.round(r.Reviewed/n*100);
  
  return `<section class="panel guide"><div class="guide-main"><small>${next?'YOUR NEXT STEP':'ALL DONE'}</small><h2>${next?`${r.Reviewed||r['In review']?'Continue with':'Start with'} ${esc(next.person)}`:'Every alert has been reviewed'}</h2><p>${next?esc(next.signal||'Accumulated unusual activity')+' · rank '+next.rank+' of '+n:'Reopen any alert from Daily alerts if you want a second look.'}</p>${next?`<a class="button primary" href="${detailLink(next)}">Open ${esc(next.person)} →</a>`:`<a class="button" href="#alerts">Back to the queue</a>`}</div><div class="guide-progress"><small>REVIEW PROGRESS</small><div class="ring" style="--p:${pct}"><span>${pct}%</span></div><p>${r.Reviewed} of ${n} reviewed · ${r['In review']} in review</p></div></section>`;
}
function chips(w){
  const r=reviewCounts(w),active=review||'';
  return `<div class="chips" role="group" aria-label="Quick review filters">${[['Unreviewed','To do'],['In review','In review'],['Reviewed','Done']].map(([k,l])=>`<button data-review="${k}" class="chip ${active===k?'on':''}" aria-pressed="${active===k}"><b>${r[k]}</b> ${l}</button>`).join('')}${(query||priority||review)?'<button data-clear class="chip clear">Clear filters</button>':''}</div>`;
}
function stepper(c){
  const s=reviewState(c),i=['Unreviewed','In review','Reviewed'].indexOf(s);
  const hint=s==='Unreviewed'?'Read the timeline and evidence, then press Begin review.':s==='In review'?'Check “What remains unknown”, then mark this alert reviewed.':'Done. Move to the next alert, or reopen this one.';
  return `<div class="stepper" aria-label="Review progress">${['Read evidence','Weigh the unknowns','Record decision'].map((t,k)=>`<div class="step ${k<i||i===2?'done':k===i?'now':''}"><b>${k<i||i===2?'✓':k+1}</b>${t}</div>`).join('<span class="bar-line"></span>')}<p>${hint}</p></div>`;
}
function reviewActions(w,c){
  const s=reviewState(c),i=w.cases.indexOf(c),prev=w.cases[i-1],next=w.cases[i+1],todo=nextCase(w,c);
  const nav=`${prev?`<a class="button" href="${detailLink(prev)}" title="Previous (←)" aria-label="Previous employee">‹</a>`:''}${next?`<a class="button" href="${detailLink(next)}" title="Next (→)" aria-label="Next employee">›</a>`:''}`;
  const main=s==='Unreviewed'?'<button id="begin" class="primary">Begin review</button><button id="complete">Mark reviewed</button>':s==='In review'?'<button id="complete" class="primary">Mark reviewed ✓</button>':`<button id="begin">Reopen</button>${todo?`<a class="button primary" href="${detailLink(todo)}">Next to review →</a>`:''}`;
  return nav+main;
}
function toast(msg){
  const b=document.body;if(!b)return;
  let t=document.getElementById('toast');
  if(!t){t=document.createElement('div');t.id='toast';t.setAttribute('role','status');b.appendChild(t);}
  t.textContent=msg;t.className='show';clearTimeout(toast.t);toast.t=setTimeout(()=>{t.className='';},2200);
}
function bindExtra(){
  document.querySelectorAll('tr[data-href]').forEach((tr,i)=>{
    if(i===cursor)tr.classList.add('cursor');
    tr.onclick=e=>{if(e.target.closest('a,button'))return;location.hash=tr.dataset.href.slice(1);};
  });
  document.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>{review=review===b.dataset.review?'':b.dataset.review;render();});
  document.querySelectorAll('[data-clear]').forEach(b=>b.onclick=()=>{query=priority=review='';render();});
  if($('#jump'))$('#jump').onclick=openPalette;
  if($('#theme'))$('#theme').onclick=()=>{try{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=t;localStorage.setItem('outofrole-theme',t);toast(t==='dark'?'Dark theme':'Light theme');}catch{}};
}
function closePalette(){document.getElementById('palette')?.remove();}
function openPalette(){
  const w=workspace();if(!w||!document.body)return;
  closePalette();
  const box=document.createElement('div');box.id='palette';
  box.innerHTML='<div class="pal-card" role="dialog" aria-label="Jump to employee"><input id="pal-q" type="search" placeholder="Jump to an employee, signal or fact ID…" aria-label="Jump to employee" autocomplete="off"><ul id="pal-list"></ul><small>↑↓ choose · Enter open · Esc close</small></div>';
  document.body.appendChild(box);
  let hits=[],at=0;
  const q=box.querySelector('#pal-q'),list=box.querySelector('#pal-list');
  const draw=()=>{const t=q.value.toLowerCase();hits=w.cases.filter(c=>!t||[c.person,c.employee,c.signal,...c.facts.map(f=>f.id)].join(' ').toLowerCase().includes(t)).slice(0,8);at=Math.min(at,Math.max(0,hits.length-1));
    list.innerHTML=hits.map((c,i)=>`<li class="${i===at?'on':''}" data-i="${i}"><b>${esc(c.person)}</b><span>${esc(c.signal||'Accumulated unusual activity')}</span><small>${badge(reviewState(c))}</small></li>`).join('')||'<li class="none">No matches</li>';
    list.querySelectorAll('li[data-i]').forEach(li=>li.onclick=()=>go(+li.dataset.i));};
  const go=i=>{const c=hits[i];if(!c)return;closePalette();location.hash=detailLink(c).slice(1);};
  q.oninput=()=>{at=0;draw();};
  q.onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();at=Math.min(hits.length-1,at+1);draw();}else if(e.key==='ArrowUp'){e.preventDefault();at=Math.max(0,at-1);draw();}else if(e.key==='Enter'){e.preventDefault();go(at);}};
  box.onclick=e=>{if(e.target===box)closePalette();};
  draw();q.focus();
}
window.addEventListener('keydown',e=>{
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openPalette();return;}
  if(e.key==='Escape'){closePalette();return;}
  const t=e.target;if(/INPUT|SELECT|TEXTAREA/.test(t?.tagName||'')||e.metaKey||e.ctrlKey||e.altKey)return;
  const w=workspace();if(!w)return;
  if(e.key==='?'){toast('/ search · j/k move · Enter open · ←/→ prev/next · m mark reviewed · ⌘K jump');return;}
  if(page==='alerts'){
    const rowsEl=document.querySelectorAll('tr[data-href]');
    if(e.key==='/'){e.preventDefault();$('#search')?.focus();}
    else if(e.key==='j'||e.key==='k'){e.preventDefault();cursor=Math.max(0,Math.min(rowsEl.length-1,cursor+(e.key==='j'?1:-1)));rowsEl.forEach((r,i)=>r.classList.toggle('cursor',i===cursor));rowsEl[cursor]?.scrollIntoView({block:'nearest'});}
    else if(e.key==='Enter'&&rowsEl[cursor]){location.hash=rowsEl[cursor].dataset.href.slice(1);}
  }else if(page==='detail'){
    const c=current(),i=w.cases.indexOf(c);
    const go=d=>{const n=w.cases[i+d];if(n)location.hash=detailLink(n).slice(1);};
    if(e.key==='ArrowRight'||e.key==='j')go(1);
    else if(e.key==='ArrowLeft'||e.key==='k')go(-1);
    else if(e.key==='m')($('#complete')||$('#begin'))?.click();
  }
});
