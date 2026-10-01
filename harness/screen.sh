#!/bin/bash
# usage: wf4/screen.sh <ABSOLUTE path of candidate stack .py (unique basename!)> <tag>
# Screen panels vs base FOB3n: akmr seat panel (160 rows) + top6x panel (120 rows), 6 workers. Result: wf4/<tag>/screen.txt
export PYTHONHASHSEED=0
PYB=~/kaggri/venv/bin/python
cd ~/kaggri/beat/v92x || exit 1
C=$1; T=$2; W=wf4/$T; mkdir -p $W; rm -f $W/screen.txt
nice -n 19 $PYB top_eval_detK1.py $W/ak.jsonl 6 160 $C > $W/screen.log 2>&1 < /dev/null
nice -n 19 $PYB top_eval_det6x.py $W/t6.jsonl 6 60 $C >> $W/screen.log 2>&1 < /dev/null
cat wf4/base_ak.jsonl $W/ak.jsonl > $W/ak_cmp.jsonl; cat wf4/base_t6.jsonl $W/t6.jsonl > $W/t6_cmp.jsonl
{ echo "== akmr seat panel (base FOB3n)"; $PYB wf4/nw_cmp.py FOB3n.py $W/ak_cmp.jsonl
  echo "== top6x panel (base FOB3n)"; $PYB wf4/nw_cmp.py FOB3n.py $W/t6_cmp.jsonl
  echo "error rows: $(cat $W/ak.jsonl $W/t6.jsonl | grep -c error)"; echo SCREENDONE; } > $W/screen.txt 2>&1
