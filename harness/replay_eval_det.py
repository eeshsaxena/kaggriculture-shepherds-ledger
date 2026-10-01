"""Evaluate candidates against RECORDED live rivals: replay the rival's recorded action tape on the recorded seed and put
each candidate in our seat. Twin games only (steps 0-143 byte-identical unit actions), subs listed.
argv: out.jsonl nproc subs(comma) cand1.py cand2.py ...   (resumable; skips done (ep, cand))
Caveat: the rival cannot react to our changed play (its tape is fixed), so rival-reactive effects are not captured."""
import sys, json, os, glob, io, contextlib
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))


def ident(rec):
    t0, t1 = rec['tapes']
    u = lambda t, i: json.dumps([(t[i] or {}).get('farmer'), (t[i] or {}).get('hands')])
    return sum(u(t0, i) == u(t1, i) for i in range(min(144, len(t0), len(t1))))


def one(args):
    import time as _tm
    _clk=[0.0]
    def _fake():
        _clk[0]+=5e-3
        return _clk[0]
    _tm.perf_counter=_fake
    path, cp = args
    rec = json.load(open(path))
    import kaggle_environments as ke
    from kaggle_environments.agent import get_last_callable
    us = rec['seat']; o = 1 - us; tape = rec['tapes'][o]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            C = get_last_callable(open(cp, encoding='utf-8').read(), path=cp)
            ag = [None, None]; ag[us] = C
            ag[o] = lambda obs, cfg=None: tape[obs['step']] if obs['step'] < len(tape) else {}
            env = ke.make("kaggriculture", configuration={"seed": rec['seed']}); env.run(ag)
        b = [env.steps[-1][k].get('reward') for k in (0, 1)]
        return {'ep': rec['ep'], 'sub': rec['sub'], 'cand': os.path.basename(cp), 'ours': b[us], 'theirs': b[o],
                'live': [rec['rewards'][us], rec['rewards'][o]]}
    except Exception as e:
        return {'ep': rec['ep'], 'cand': os.path.basename(cp), 'error': repr(e)[:200]}


if __name__ == '__main__':
    out, npr, subs = sys.argv[1], int(sys.argv[2]), {int(s) for s in sys.argv[3].split(',')}
    cands = sys.argv[4:]
    done = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l)
            if 'ours' in r: done.add((r['ep'], r['cand']))
    games = []
    for f in sorted(glob.glob(os.path.join(HERE, 'compact', 'o_*.json'))):
        rec = json.load(open(f))
        if rec.get('sub') in subs and rec.get('seat') is not None and ident(rec) >= 120:
            games.append(f)
    jobs = [(g, c) for g in games for c in cands if (int(os.path.basename(g)[2:-5]), os.path.basename(c)) not in done]
    print('twin games', len(games), 'jobs', len(jobs), flush=True)
    with Pool(npr, maxtasksperchild=8) as pool, open(out, 'a') as fo:
        for i, r in enumerate(pool.imap_unordered(one, jobs)):
            fo.write(json.dumps(r) + '\n'); fo.flush()
            if i % 50 == 0: print(i, flush=True)
    print('DONE', flush=True)
