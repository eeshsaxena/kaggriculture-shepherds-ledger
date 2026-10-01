#!/bin/bash
# usage: wfslot.sh <cmd...>
# Runs <cmd> while holding one of 4 box slot locks (each slot = at most 6 worker processes, 24 total for the workflow).
# Blocks (polling every 20 s) until a slot is free. Exit code = the command's exit code.
while true; do
  for i in 0 1 2 3 4; do
    exec 9>/tmp/kgwf4_slot$i.lock
    if flock -n 9; then
      echo "slot $i acquired $(date -u +%H:%M:%S)" >&2
      "$@"; rc=$?
      flock -u 9; exec 9>&-
      exit $rc
    fi
    exec 9>&-
  done
  sleep 20
done
