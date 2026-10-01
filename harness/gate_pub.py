'''Release gates for an agent FILE, all in the REAL kaggle_environments engine.
 (d) timing: the file is loaded exactly as the engine loads it (get_last_callable), wrapped with a timer and played
     through env.run; reports first-call ms, p99 and max per step, over games vs several opponents, both seats.
 (e) crash fuzz: malformed / edge observations must return an action dict without raising.
 (l) leak: N consecutive episodes with ONE loaded copy vs a fresh copy per episode (same seeds, same opponent files);
     any bank difference means module state leaks across episodes.
usage: gate_pub.py CAND.py OPP1.py [OPP2.py ...]'''
import sys, os, io, json, time, copy, contextlib
from multiprocessing import Pool
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable

CAND = os.path.abspath(sys.argv[1]); OPPS = [os.path.abspath(x) for x in sys.argv[2:]]


def load(path):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return get_last_callable(open(path).read())


def timed_game(job):
    opp, seed, me = job
    inner = load(CAND); ts = []
    def ag(obs, cfg):
        t0 = time.perf_counter(); a = inner(obs, cfg); ts.append(time.perf_counter() - t0); return a
    agents = [None, None]; agents[me] = ag; agents[1 - me] = opp
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env = make("kaggriculture", configuration={"seed": seed}, debug=True); env.run(agents)
    last = env.steps[-1]
    return dict(opp=os.path.basename(opp), seed=seed, me=me, a=last[me]["reward"], b=last[1 - me]["reward"],
                st=[last[0]["status"], last[1]["status"]], n=len(env.steps), first_ms=ts[0] * 1000 if ts else None,
                ms=sorted(t * 1000 for t in ts))


def leak_run(fresh):
    shared = None if fresh else load(CAND); out = []
    for i, seed in enumerate(range(8101, 8121)):
        me = i % 2; opp = OPPS[i % len(OPPS)]
        a = load(CAND) if fresh else shared
        agents = [None, None]; agents[me] = a; agents[1 - me] = opp
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            env = make("kaggriculture", configuration={"seed": seed}, debug=True); env.run(agents)
        out.append(int(env.steps[-1][me]["reward"] or 0))
    return out


def fuzz():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env = make("kaggriculture", configuration={"seed": 8201}, debug=True)
        obs_log = []
        def rec(obs, cfg):
            if int(obs["step"]) in (0, 1, 300, 717, 718): obs_log.append((copy.deepcopy(obs), cfg))
            return {"farmer": ["PASS"], "hands": [], "market": []}
        env.run([rec, "random"] if False else [rec, rec])
    fails = []
    cases = []
    for obs, cfg in obs_log:
        cases.append(("step%d" % int(obs["step"]), obs))
        o = copy.deepcopy(obs); o["farms"][o["player"]]["hands"] = []; cases.append(("nohands%d" % int(obs["step"]), o))
        o = copy.deepcopy(obs); o["farms"][o["player"]]["money"] = 0; cases.append(("zeromoney%d" % int(obs["step"]), o))
        o = copy.deepcopy(obs); o["private"]["shed"] = {}; cases.append(("emptyshed%d" % int(obs["step"]), o))
        o = copy.deepcopy(obs); o["town"]["unlocked_shops"] = []; cases.append(("noshops%d" % int(obs["step"]), o))
        o = copy.deepcopy(obs)
        for row in o["farms"][o["player"]]["tiles"]:
            for j in range(len(row)): row[j] = {"kind": "WEED"}
        cases.append(("allweed%d" % int(obs["step"]), o))
    for name, o in cases:
        a = load(CAND)   # fresh copy per case so one case cannot poison the next
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                r = a(o, obs_log[0][1])
            if not isinstance(r, dict): fails.append((name, "returned %s" % type(r).__name__))
        except Exception as ex:
            fails.append((name, repr(ex)[:120]))
    return len(cases), fails


if __name__ == "__main__":
    jobs = [(o, s, s % 2) for o in OPPS for s in range(8001, 8013)]
    with Pool(min(12, len(jobs))) as p:
        res = p.map(timed_game, jobs)
        leak = p.map(leak_run, [False, True])
    allms = sorted(x for r in res for x in r["ms"])
    p99 = allms[int(0.99 * (len(allms) - 1))]
    bad = [r for r in res if r["st"] != ["DONE", "DONE"] or r["n"] != 720]
    print("GATE (d) timing: games %d, calls %d, first-call max %.0f ms, p99 %.1f ms, max %.1f ms, non-DONE %d" % (
        len(res), len(allms), max(r["first_ms"] for r in res), p99, allms[-1], len(bad)))
    for o in OPPS:
        rr = [r for r in res if r["opp"] == os.path.basename(o)]
        print("     vs %-28s W/L %d/%d" % (os.path.basename(o), sum(r["a"] > r["b"] for r in rr), sum(r["a"] < r["b"] for r in rr)))
    d = [x - y for x, y in zip(leak[0], leak[1])]
    print("GATE (l) leak: loaded-once vs fresh differ in %d of %d episodes, first at %s, drift %+d" % (
        sum(1 for x in d if x), len(d), next((i for i, x in enumerate(d) if x), None), sum(d)))
    n, fails = fuzz()
    print("GATE (e) fuzz: %d cases, %d raised/bad" % (n, len(fails)))
    for f in fails[:12]: print("     ", f)
