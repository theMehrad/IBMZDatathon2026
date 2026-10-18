#!/bin/bash
# Final OutOfRole setting: never-seen-site + boss-PC inputs at weight 5, with export.
# Usage: bash test/run_best.sh 5.2      (or 4.2)
REL=${1:-5.2}
python test/outofrole_email.py "$REL" --feats=n_new_site,n_boss_pc --w=5 --export