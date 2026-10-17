# Review brief: OutOfRole feasibility study

You are reviewing a student team's pre-event feasibility study for the IBM Z Datathon 2026 (track "AI Secured: Innovation Without Exposure"). The build happens on Oct 17-18 on an IBM LinuxONE server; this study ran on a laptop to decide what to build.

## Files here
- `OutOfRole_Feasibility.ipynb`: the full study, executed, with code, outputs and a "Finding" cell after every step (14 steps). Read the outputs; the data files are NOT available to you, so do not try to re-run cells.
- `OutOfRole_Plan.md`: the resulting build plan, the changes from the original idea, and a per-step findings table.
- `Research_Findings.md`: the literature, industry and platform research that motivated several steps.

## What the study does
- Data: CMU SEI CERT Insider Threat Test Dataset r4.2 (1,000 users, 70 insiders, scenarios 1-3) and r5.2 (2,000 users, 99 insiders, adds scenario 4: logging into colleagues' computers).
- Goal: rank users so insiders rise to the top, mostly label-free; test whether an implicit-feedback ALS recommender ("access surprising for someone like you") adds value.
- Protocol: user-level ranking; train window ends before the first malicious event (r4.2: 2010-06-01, r5.2: 2010-04-01); answer key only for evaluation; LDAP departures never used. Metrics: P@20, hits@70, AP, AUC, per-scenario count in top 100; leave-one-scenario-out (LOSO) for trained combiners.
- Conclusion: four specialist alert queues (own-history percentile spike, unusual-weeks drift, an ownership rule for personal computers, ALS peer-of-item on websites) instead of one fused score.

## What we want from you
Be a demanding senior reviewer in ML evaluation and security analytics. Prioritize problems that would change a conclusion or embarrass the team in front of IBM judges. For every point, cite the notebook step/cell and quote the code line or output number you rely on. Separate what you verified from what you suspect.
