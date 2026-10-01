"""Deterministic cross-episode leak test: loaded-once vs fresh copy, 20 episodes, fake perf_counter (no timing noise).
usage: PYTHONHASHSEED=0 python gate_leak_det.py CAND.py OPP1.py [OPP2.py ...]"""
import sys, os, io, contextlib, time
_clk = [0.0]
def _fake():
    _clk[0] += 5e-3
    return _clk[0]
time.perf_counter = _fake
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
CAND = os.path.abspath(sys.argv[1]); OPPS = [os.path.abspath(x) for x in sys.argv[2:]]
def load(path):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return get_last_callable(open(path, encoding='utf-8').read())
def leak_run(fresh):
    shared = None if fresh else load(CAND); out = []
    for i, seed in enumerate(range(8101, 8121)):
        me = i % 2; opp = OPPS[i % len(OPPS)]
        a = load(CAND) if fresh else shared
        agents = [None, None]; agents[me] = a; agents[1 - me] = opp
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env = make("kaggriculture", configuration={"seed": seed}, debug=True); env.run(agents)
        out.append((int(env.steps[-1][me]["reward"] or 0), int(env.steps[-1][1 - me]["reward"] or 0), env.steps[-1][me]["status"]))
    return out
f = leak_run(True); s = leak_run(False)
diff = [i for i in range(20) if f[i][:2] != s[i][:2]]
print('LEAK-DET: differ in %d of 20 episodes, first at %s, drift %+d, statuses %s' % (len(diff), diff[0] if diff else None, sum(s[i][0] - f[i][0] for i in range(20)), sorted({x[2] for x in f + s})))
for i in diff[:5]: print('  ep', i, 'fresh', f[i][:2], 'shared', s[i][:2])
