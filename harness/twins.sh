#!/bin/bash
# usage: wf4/twins.sh <ABSOLUTE candidate .py (unique basename)> <tag>
# 1036 live TWIN replays (recorded rival tapes, candidate in our seat) vs base FOB3 rows (re_F3.jsonl). 6 workers. Result wf4/<tag>/twins.txt
export PYTHONHASHSEED=0
PYB=~/kaggri/venv/bin/python
cd ~/kaggri/beat/v92x || exit 1
C=$1; T=$2; W=wf4/$T; mkdir -p $W; rm -f $W/twins.txt
SUBS=56610695,56610703,56629308,56643627,56643623,56571643,56567088,56649374,56649367,56655452,56655408,56670971,56682480,56693033
nice -n 19 $PYB replay_eval_det.py $W/tw.jsonl 6 $SUBS $C > $W/twins.log 2>&1 < /dev/null
grep '"cand": "FOB3.py"' re_F3.jsonl | grep -v error > $W/b_tw.jsonl
cat $W/b_tw.jsonl $W/tw.jsonl > $W/tw_cmp.jsonl
{ echo "== 1036 live twins (base FOB3; FOB3n is identical to FOB3 on twins: the JIT gate needs NT)"; $PYB wf4/re_cmp.py $W/tw_cmp.jsonl FOB3.py | cut -c1-260
  echo "error rows: $(grep -c error $W/tw.jsonl)"; echo TWINSDONE; } > $W/twins.txt 2>&1
