"""Loss report for our live subs from exact replays (v92x/rec). argv: live_both.json
Per loss: opponent, twin/non-twin, first divergence step, margin decomposition (revenue per item, spend per category,
hires+land residual), d14 census both sides, quadrants, and the first day the money gap turned."""
import json, os, sys, collections

ITEMS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
rows = json.load(open(sys.argv[1]))
L = sorted([r for r in rows if r['me'] < r['op']], key=lambda r: r['me'] - r['op'])
agg = collections.defaultdict(list)
missing = 0
for r in L:
    p = 'v92x/rec/r_%d.json' % r['ep']
    if not os.path.exists(p):
        missing += 1
        print('%d %-10s %+6d vs %s (%.0f): not recorded yet' % (r['ep'], r['name'], r['me'] - r['op'], r['op_team_name'][:18], r['op_rating'] or 0))
        continue
    R = json.load(open(p)); us = R['seat']; th = 1 - us
    rev = {s: collections.Counter() for s in (us, th)}; units = {s: collections.Counter() for s in (us, th)}
    spend = {s: collections.Counter() for s in (us, th)}
    for s in (us, th):
        for t, op, item, n, v in R['units'][str(s)]:
            if op == 'SELL':
                rev[s][item] += v; units[s][item] += n
            else:
                spend[s][op.split('_')[-1] + ':' + item] += v
    res = {s: R['rewards'][s] - 3000 - sum(rev[s].values()) + sum(spend[s].values()) for s in (us, th)}
    kind = 'TWIN' if R['identical_open'] >= 120 else ('mid' if R['identical_open'] >= 60 else 'NON-TWIN')
    comp = {i: rev[us][i] - rev[th][i] for i in ITEMS}
    comp['spend'] = -(sum(spend[us].values()) - sum(spend[th].values()))
    comp['hires+land'] = res[us] - res[th]
    worst = sorted(comp.items(), key=lambda kv: kv[1])[:4]
    gap = [R['days'][str(us)][d]['money'] - R['days'][str(th)][d]['money'] for d in range(30)]
    cu = R['days'][str(us)][14]['census']; ct = R['days'][str(th)][14]['census']
    ks = ('COW', 'SHEEP', 'GOOSE', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT', 'MELON')
    print('%d %-10s %+6d vs %-18s (%.0f) %s ident %3d  shops %s' % (r['ep'], r['name'], r['me'] - r['op'], r['op_team_name'][:18], r['op_rating'] or 0, kind,
          R['identical_open'], ','.join(s[1][:5] for s in R['shops'][:6])))
    print('    worst components: ' + '  '.join('%s %+d' % kv for kv in worst) + '   (units us|them: ' +
          ' '.join('%s %d|%d' % (i[:4], units[us][i], units[th][i]) for i, _ in worst if i in ITEMS) + ')')
    print('    d14 us  ' + ' '.join('%s%d' % (k[:3], cu.get(k, 0)) for k in ks) + ' q%d h%d' % (R['days'][str(us)][14]['quads'], R['days'][str(us)][14]['hands']) +
          ' | them ' + ' '.join('%s%d' % (k[:3], ct.get(k, 0)) for k in ks) + ' q%d h%d' % (R['days'][str(th)][14]['quads'], R['days'][str(th)][14]['hands']))
    print('    money gap: ' + ' '.join('d%d %+d' % (d, gap[d]) for d in (9, 13, 17, 20, 23, 26, 28, 29)))
    for k, v in comp.items():
        agg[(kind, k)].append(v)
    agg[(kind, 'margin')].append(r['me'] - r['op'])
print('\nmissing', missing)
for kind in ('TWIN', 'mid', 'NON-TWIN'):
    n = len(agg[(kind, 'margin')])
    if not n:
        continue
    print('== %s losses n=%d mean margin %+.0f' % (kind, n, sum(agg[(kind, 'margin')]) / n))
    print('   mean components: ' + '  '.join('%s %+.0f' % (k, sum(agg[(kind, k)]) / n) for k in ITEMS + ['spend', 'hires+land']))
