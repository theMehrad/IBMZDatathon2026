'use strict';

function pipelinePanel() {
  if (sample || !remote.pipeline) return '';
  const p = remote.pipeline;
  const w = workspace();
  const saved = w && !activity();
  const scores = saved ? w.cases.filter(c => Number.isFinite(c.score)).length : 0;
  const accepted = saved ? w.cases.filter(c => c.status === 'Accepted').length : 0;
  const savedNotice = saved ? `<section class="panel"><div class="panel-head"><h2>Saved runner results loaded</h2>${badge('READ ONLY')}</div><div class="note"><p>${scores} saved detector score${scores === 1 ? '' : 's'} · ${accepted} accepted Granite assessment${accepted === 1 ? '' : 's'}${w.attempt ? ` · attempt ${esc(w.attempt)}` : ''}.</p><p>Viewing these results does not require a configured model or a new analysis run. The optional setup below applies only to generating new results.</p></div></section>` : '';
  const setupBadges = `${badge(p.scoring_ready ? 'NEW SCORING READY' : 'NEW SCORING NOT READY')} ${badge(p.granite_ready ? 'NEW INFERENCE READY' : 'NEW INFERENCE NOT CONFIGURED')}`;
  return `${savedNotice}<details class="panel pipeline" ${page === 'setup' || !saved ? 'open' : ''}>
    <summary>${saved ? 'Setup for new analysis (optional)' : `Setup for generating scored results ${setupBadges}`}</summary>
    ${saved ? `<div class="note">${setupBadges}<p>These checks do not affect the saved results already displayed.</p></div>` : ''}
    <div class="two-col note"><div><h2>Generate new detector scores</h2>
      <p>${saved ? 'Your saved detector scores are already loaded. These requirements apply only when preparing a different day or a new run.' : 'The project detector exports its original daily list and running scores. Raw logon records alone cannot reproduce those scores.'}</p>
      ${p.scoring_blockers.length ? `<ul>${p.scoring_blockers.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p>Required processed tables and scoring dependencies are available.</p>'}
      <h2>Processed tables</h2><ul>${p.tables.map(t => `<li>${esc(t.name)}: ${t.readable ? 'ready' : t.complete ? 'reader unavailable' : 'missing or incomplete'} (${esc(t.format)})</li>`).join('')}</ul>
    </div><div><h2>Run new Granite inference</h2>
      <p>A model file is needed only to generate new assessments. Saved assessments remain viewable without it.</p>
      <p>Granite selects an allowed label and supporting fact IDs. It cannot change ranks, remove employees, or supply narrative facts.</p>
      ${p.granite_blockers.length ? `<ul>${p.granite_blockers.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p>Runtime and model file are available. Native inference still needs an explicit run.</p>'}
      <p>Accepted means the response passed validation; it does not establish intent or classification accuracy.</p>
    </div></div>
    <div class="note"><h2>Optional commands for a new run</h2><p>Do not run these merely to view saved results. Run these from the repository on the machine holding the processed tables and model. Preparation executes the reference scorer; inference reuses its packs. Neither command runs Spark. Replace the example date and paths with your intended replay day and existing files.</p>
      <pre>python3 code/dashboard_pipeline.py check
python3 code/dashboard_pipeline.py prepare --release ${esc(p.release)} --day ${esc(remote.workspace && !activity() ? remote.workspace.day : '2010-08-02')}
python3 code/dashboard_pipeline.py infer --run-dir /path/to/existing-run --model /path/to/granite.gguf --max-cases 1</pre>
      <p>Inference starts with one diagnostic case and preserves the remaining queue as Not inferred. Use --model-mode completion only for the supplied base model. Refresh Runner outputs after results are saved.</p>
    </div>
  </details>`;
}

function inferencePanel(w) {
  if (sample || activity() || !w) return '';
  const progress = w.progress || {};
  return `<section class="panel"><div class="panel-head"><h2>Detector scores and Granite progress</h2><small>RANKS PRESERVED</small></div>
    <div class="note"><p>${esc(w.scoring_contract || 'Original detector running scores. Not probabilities or scores out of 100.')}</p>
      <h2>Highest-ranked detector scores</h2>
      <div class="score-list">${w.cases.slice(0,5).map(c => `<div class="score-row"><a href="${detailLink(c)}">${esc(c.person)}</a><meter min="0" max="${Math.max(1,...w.cases.map(x => x.score ?? 0))}" value="${c.score ?? 0}" aria-label="${esc(c.person)} running score"></meter><span class="mono" title="${esc(c.score)}">${num(c.score)}</span></div>`).join('') || '<p>No scored alerts in this exported queue.</p>'}</div>
      <div class="actions">${['Accepted','Fallback','Not inferred'].map(s => badge(`${progress[s] ?? 0} ${s}`)).join('')}</div>
      <p>Accepted responses cite known evidence. Fallback and unprocessed entries retain their original detector score and rank.</p>
      <label>Inference attempt <select id="attempt" aria-label="Granite inference attempt" ${(w.attempts || []).length ? '' : 'disabled'}>
      ${(w.attempts || []).length ? w.attempts.map(a => `<option value="${esc(a)}" ${w.attempt === a ? 'selected' : ''}>${esc(a)}</option>`).join('') : '<option>No inference results yet</option>'}</select></label>
      <p>Model: ${esc(w.model?.name || 'Not recorded')} · Mode: ${esc(w.model?.mode || '—')} · Structured output: ${w.model?.structured_output === true ? 'enabled' : w.model?.structured_output === false ? 'disabled' : 'not recorded'}</p>
      ${w.model?.sha256 ? `<details><summary>Model provenance</summary><p class="mono">SHA-256: ${esc(w.model.sha256)}</p></details>` : ''}
    </div>
  </section>`;
}
