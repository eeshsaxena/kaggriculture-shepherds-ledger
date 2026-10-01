"""Local gauntlet on the real engine (seat-symmetric engine => one seat per pairing).
argv: out.jsonl lo-hi nproc FIELD(comma list of files) cand1.py cand2.py ...
Every candidate plays every field agent on every seed (candidate in seat 0). Skips a candidate vs itself.
Resumable: games already in out.jsonl are skipped. Honors a PAUSE file (thermal guard)."""
import sys, json, os, time
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
PAUSE = os.path.join(HERE, "PAUSE")

def init():
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
    except Exception:
        pass

def one(args):
    seed, a, b = args
    import time as _tm
    _clk=[0.0]
    def _fake():
        _clk[0]+=5e-3
        return _clk[0]
    _tm.perf_counter=_fake
    while os.path.exists(PAUSE):
        time.sleep(10)
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import kaggle_environments as ke
        from kaggle_environments.agent import get_last_callable
    t = time.time()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            A = get_last_callable(open(a, encoding="utf-8").read(), path=a)
            B = get_last_callable(open(b, encoding="utf-8").read(), path=b)
            env = ke.make("kaggriculture", configuration={"seed": seed})
            env.run([A, B])
        last = env.steps[-1]
        errs = 0
        for k, v in getattr(A, "__globals__", {}).items():
            if k.endswith("_REPORT") and isinstance(v, dict):
                errs += sum(x for y, x in v.items() if "error" in str(y) and isinstance(x, int))
        return {"seed": seed, "p0": os.path.basename(a), "p1": os.path.basename(b),
                "banks": [last[s].get("reward") for s in range(2)],
                "status": [last[s].get("status") for s in range(2)], "errs": errs, "sec": round(time.time() - t, 1)}
    except Exception as e:
        return {"seed": seed, "p0": os.path.basename(a), "p1": os.path.basename(b), "error": repr(e)[:300]}

if __name__ == "__main__":
    out = sys.argv[1]; lo, hi = map(int, sys.argv[2].split("-")); npr = int(sys.argv[3])
    field = sys.argv[4].split(","); cands = sys.argv[5:]
    done = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l)
            if "banks" in r: done.add((r["seed"], r["p0"], r["p1"]))
    jobs = [(s, c, f) for s in range(lo, hi + 1) for c in cands for f in field
            if os.path.basename(c) != os.path.basename(f) and (s, os.path.basename(c), os.path.basename(f)) not in done]
    print("jobs", len(jobs), "already", len(done), flush=True)
    with Pool(npr, initializer=init, maxtasksperchild=8) as pool, open(out, "a") as fo:
        for i, r in enumerate(pool.imap_unordered(one, jobs)):
            fo.write(json.dumps(r) + "\n"); fo.flush()
            if i % 20 == 0: print(i, time.strftime("%H:%M:%S"), flush=True)
    print("DONE", flush=True)
