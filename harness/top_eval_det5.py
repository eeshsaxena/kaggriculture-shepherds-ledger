"""Pinned-world seat substitution vs recorded TOP-team tapes.
For each compact_top game and each seat s: candidate plays seat s, the other seat replays its recorded tape; the engine is
pinned to the recorded shop sequence and the rival's recorded weed spawns (our weeds use the engine rng).
argv: out.jsonl nproc maxgames cand1.py [cand2.py ...]   (cand 'ORIG' = replay the recorded tape in seat s: exactness check)"""
import sys, json, os, glob, io, contextlib
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
_PIN = {}
def install():
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    if getattr(K, '_pin_installed', False): return K
    o_sw, o_eod = K._spawn_weeds, K._end_of_day
    def sw(farm, board_size, weed_chance, rng):
        if _PIN and id(farm) == _PIN.get('rival_farm_id'):
            for y in range(board_size):
                for x in range(board_size):
                    if farm['tiles'][y][x] is None:
                        rng.random()          # keep the shared rng stream aligned with the engine
            for d, x, y in _PIN['weeds'].get(_PIN['day'], ()):
                if farm['tiles'][y][x] is None:
                    farm['tiles'][y][x] = {'kind': 'WEED'}
            return
        return o_sw(farm, board_size, weed_chance, rng)
    def eod(state, env, day):
        if _PIN:
            _PIN['day'] = day; _PIN['rival_farm_id'] = id(state[0].observation.farms[_PIN['rival']])
        r = o_eod(state, env, day)
        if _PIN:
            sh = _PIN['shops'].get(str(day + 1)) or _PIN['shops'].get(day + 1)
            if sh is not None:
                town = state[0].observation.town
                town['unlocked_shops'][:] = list(sh)
        return r
    K._spawn_weeds = sw; K._end_of_day = eod; K._pin_installed = True
    return K
def one(args):
    path, seat, cp = args
    import time as _tm
    _clk=[0.0]
    def _fake():
        _clk[0]+=5e-3
        return _clk[0]
    _tm.perf_counter=_fake
    rec = json.load(open(path))
    import kaggle_environments as ke
    from kaggle_environments.agent import get_last_callable
    o = 1 - seat
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            install()
            _PIN.clear()
            wd = {}
            for d, x, y in rec['weeds'][str(o)] if isinstance(rec['weeds'], dict) and str(o) in rec['weeds'] else rec['weeds'][o]:
                wd.setdefault(d, []).append((d, x, y))
            _PIN.update(rival=o, weeds=wd, shops=rec['shops_by_day'], day=-1)
            tape_o = rec['tapes'][o]
            ag = [None, None]
            if cp == 'ORIG':
                tape_s = rec['tapes'][seat]; ag[seat] = lambda obs, cfg=None: tape_s[obs['step']] if obs['step'] < len(tape_s) else {}
            else:
                ag[seat] = get_last_callable(open(cp, encoding='utf-8').read(), path=cp)
            ag[o] = lambda obs, cfg=None: tape_o[obs['step']] if obs['step'] < len(tape_o) else {}
            env = ke.make('kaggriculture', configuration={'seed': rec['seed']}); env.run(ag)
            _PIN.clear()
        b = [env.steps[-1][k].get('reward') for k in (0, 1)]
        return {'ep': rec['ep'], 'seat': seat, 'cand': os.path.basename(cp), 'ours': b[seat], 'theirs': b[o],
                'rival': rec['names'][o], 'replaced': rec['names'][seat], 'orig': rec['rewards']}
    except Exception as e:
        _PIN.clear()
        return {'ep': rec['ep'], 'seat': seat, 'cand': os.path.basename(cp), 'error': repr(e)[:200]}
if __name__ == '__main__':
    out, npr, maxg = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); cands = sys.argv[4:]
    done = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l)
            if 'ours' in r: done.add((r['ep'], r['seat'], r['cand']))
    games = sorted(glob.glob(os.path.join(HERE, 'compact_top5', 'o_*.json')))[:maxg]
    jobs = [(g, s, c) for g in games for s in (0, 1) for c in cands
            if (int(os.path.basename(g)[2:-5]), s, os.path.basename(c)) not in done]
    print('games', len(games), 'jobs', len(jobs), flush=True)
    with Pool(npr, maxtasksperchild=8) as pool, open(out, 'a') as f:
        for i, r in enumerate(pool.imap_unordered(one, jobs)):
            f.write(json.dumps(r) + '\n'); f.flush()
            if i % 50 == 0: print(i, flush=True)
    print('DONE', flush=True)
