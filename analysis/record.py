"""Replay compact live games exactly on the real engine and record every executed market unit per player.
argv: out_dir nproc compact1.json [compact2.json ...]   (writes out_dir/r_<ep>.json, skips existing)
Per game: reproduced flag, shops with unlock day, per-player executed SELL / BUY_PRODUCT / BUY_SEED / BUY_ANIMAL units
as [t, item, units, value] where t is the obs step whose action placed the order (same index as the tape),
money and census at the end of every day, and how many of steps 1-143 have identical unit actions on both seats."""
import sys, json, os, io, contextlib, collections
from multiprocessing import Pool

LOG = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
CUR = {}


def install():
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    if getattr(K, '_rec_installed', False):
        return K
    orig_pm, orig_cu = K._process_market, K._commit_unit

    def pm(state, env):
        farms = state[0].observation.farms
        CUR['map'] = {id(farms[0]): 0, id(farms[1]): 1}
        CUR['step'] = int(state[0].observation.step)
        return orig_pm(state, env)

    def cu(op, item, price, farm, private, market, shed_capacity=100):
        ok = orig_cu(op, item, price, farm, private, market, shed_capacity)
        if ok and 'map' in CUR:
            p = CUR['map'].get(id(farm))
            if p is not None:
                e = LOG[(p, op, item)][CUR['step']]
                e[0] += 1; e[1] += price
        return ok
    K._process_market = pm; K._commit_unit = cu; K._rec_installed = True
    return K


def one(args):
    path, out_dir = args
    rec = json.load(open(path))
    out = os.path.join(out_dir, 'r_%d.json' % rec['ep'])
    if os.path.exists(out):
        return 'skip'
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import kaggle_environments as ke
        install()
    LOG.clear(); CUR.clear()
    tapes = rec['tapes']
    bots = [(lambda tp: (lambda obs, cfg=None: tp[obs['step']] if obs['step'] < len(tp) else {}))(tapes[s]) for s in (0, 1)]
    env = ke.make("kaggriculture", configuration={"seed": rec['seed']})
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env.run(bots)
    st = env.steps
    rewards = [st[-1][k].get('reward') for k in (0, 1)]
    # find the step offset between the logged engine step and the tape index using SELL orders
    raw = collections.defaultdict(list)
    for (p, op, item), d in LOG.items():
        for t, (u, v) in d.items():
            raw[p].append([t, op, item, u, v])
    off_votes = collections.Counter()
    for p in (0, 1):
        for t, op, item, u, v in raw[p]:
            if op != 'SELL':
                continue
            for off in (-1, 0, 1):
                ti = t + off
                if 0 <= ti < len(tapes[p]) and any(o and o[0] == 'SELL' and len(o) > 1 and o[1] == item for o in (tapes[p][ti] or {}).get('market') or []):
                    off_votes[off] += 1
    off = off_votes.most_common(1)[0][0] if off_votes else 0
    res = {'ep': rec['ep'], 'sub': rec.get('sub'), 'seat': rec.get('seat'), 'seed': rec['seed'], 'names': rec.get('names'),
           'rewards': rec['rewards'], 'reproduced': rewards == rec['rewards'], 'offset': off, 'off_votes': dict(off_votes)}
    final_shops = st[-1][0]['observation']['town']['unlocked_shops']
    res['shops'] = [[3 * i + 2, s] for i, s in enumerate(final_shops)]
    res['units'] = {p: sorted([[t + off, op, item, u, v] for t, op, item, u, v in raw[p]]) for p in (0, 1)}
    days = {0: [], 1: []}
    for d in range(30):
        i = min(d * 24 + 23, len(st) - 1)
        o = st[i][0]['observation']
        for p in (0, 1):
            f = o['farms'][p]; c = collections.Counter()
            for row in f['tiles']:
                for tl in row:
                    if isinstance(tl, dict): c[tl.get('animal') or tl.get('crop') or tl.get('kind')] += 1
                    elif tl is None: c['EMPTY'] += 1
            days[p].append({'money': f['money'], 'hands': len(f['hands']), 'quads': len(f.get('unlocked_quadrants') or []), 'census': dict(c)})
    res['days'] = days
    res['prices_day'] = [st[min(d * 24 + 23, len(st) - 1)][0]['observation']['market']['prices'] for d in range(30)]
    u = lambda i, s: json.dumps([(tapes[s][i] or {}).get('farmer'), (tapes[s][i] or {}).get('hands')])
    res['identical_open'] = sum(u(i, 0) == u(i, 1) for i in range(0, min(144, len(tapes[0]), len(tapes[1]))))
    json.dump(res, open(out, 'w'))
    return 'ok' if res['reproduced'] else 'NOREPRO'


if __name__ == '__main__':
    out_dir = sys.argv[1]; npr = int(sys.argv[2]); os.makedirs(out_dir, exist_ok=True)
    jobs = [(p, out_dir) for p in sys.argv[3:]]
    c = collections.Counter()
    with Pool(npr, maxtasksperchild=10) as pool:
        for i, r in enumerate(pool.imap_unordered(one, jobs)):
            c[r] += 1
            if i % 25 == 0: print(i, dict(c), flush=True)
    print('DONE', dict(c), flush=True)
