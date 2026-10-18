'use strict';

function pipelinePanel() {
  if (sample || !remote.pipeline) return '';
  const p = remote.pipeline;
  return `<details class="panel pipeline" ${!remote.workspace || activity() ? 'open' : ''}>
    <summary>Scoring and Granite readiness ${badge(p.scoring_ready ? 'SCORER READY' : 'SCORES UNAVAILABLE')} ${badge(p.granite_ready ? 'GRANITE READY' : 'GRANITE UNAVAILABLE')}</summary>
    <div class="two-col note"><div><h2>Detector scores</h2>
      <p>The project detector exports its original daily list and running scores. Raw logon records alone cannot reproduce those scores.</p>
      ${p.scoring_blockers.length ? `<ul>${p.scoring_blockers.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p>Required processed tables and scoring dependencies are available.</p>'}
      <h2>Processed tables</h2><ul>${p.tables.map(t => `<li>${esc(t.name)}: ${t.readable ? 'ready' : t.complete ? 'reader unavailable' : 'missing or incomplete'} (${esc(t.format)})</li>`).join('')}</ul>
    </div><div><h2>IBM Granite assessments</h2>
      <p>Granite selects an allowed label and supporting fact IDs. It cannot change ranks, remove employees, or supply narrative facts.</p>
      ${p.granite_blockers.length ? `<ul>${p.granite_blockers.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p>Runtime and model file are available. Native inference still needs an explicit run.</p>'}
      <p>Accepted means the response passed validation; it does not establish intent or classification accuracy.</p>
    </div></div>
    <div class="note"><h2>Use the existing runner</h2><p>Run these from the repository on the machine holding the processed tables and model. Preparation executes the reference scorer; inference reuses its packs. Neither command runs Spark. Replace the example date and paths with your intended replay day and existing files.</p>
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
