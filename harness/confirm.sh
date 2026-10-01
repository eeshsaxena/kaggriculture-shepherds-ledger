#!/bin/bash
# usage: wf4/confirm.sh <ABSOLUTE path of candidate stack .py (unique basename!)> <tag>
# Confirm panels vs base FOB3n: feel-the-agi panel (160 rows) + top5 panel (120 rows) + public field (144 games), 6 workers.
# Result: wf4/<tag>/confirm.txt
export PYTHONHASHSEED=0
PYB=~/kaggri/venv/bin/python
cd ~/kaggri/beat/v92x || exit 1
C=$1; T=$2; W=wf4/$T; mkdir -p $W; rm -f $W/confirm.txt
nice -n 19 $PYB top_eval_detA.py $W/agi.jsonl 6 80 $C > $W/confirm.log 2>&1 < /dev/null
nice -n 19 $PYB top_eval_det5.py $W/t5.jsonl 6 60 $C >> $W/confirm.log 2>&1 < /dev/null
cd ../pub2
F=$(ls cands5/p_*.py | grep -v icefire | grep -v harvest2 | tr '\n' ',' | sed 's/,$//')
nice -n 19 $PYB gauntlet_det.py ../v92x/$W/gN.jsonl 1400-1415 6 $F $C >> ../v92x/$W/confirm.log 2>&1 < /dev/null
cd ../v92x
grep '"cand": "FOB3n.py"' f3n_agi.jsonl | grep -v error > $W/b_agi.jsonl; grep '"cand": "FOB3n.py"' f3n_t5.jsonl | grep -v error > $W/b_t5.jsonl
grep '"p0": "FOB3n.py"' ../pub2/f3n_gN.jsonl > $W/b_gN.jsonl
cat $W/b_agi.jsonl $W/agi.jsonl > $W/agi_cmp.jsonl; cat $W/b_t5.jsonl $W/t5.jsonl > $W/t5_cmp.jsonl; cat $W/b_gN.jsonl $W/gN.jsonl > $W/gN_cmp.jsonl
{ echo "== feel-the-agi panel (base FOB3n)"; $PYB wf4/nw_cmp.py FOB3n.py $W/agi_cmp.jsonl
  echo "== top5 panel (base FOB3n)"; $PYB wf4/nw_cmp.py FOB3n.py $W/t5_cmp.jsonl
  echo "== public field (base FOB3n)"; $PYB wf4/gcmp.py $W/gN_cmp.jsonl FOB3n.py
  echo "error rows: $(cat $W/agi.jsonl $W/t5.jsonl | grep -c error)"; echo CONFIRMDONE; } > $W/confirm.txt 2>&1
