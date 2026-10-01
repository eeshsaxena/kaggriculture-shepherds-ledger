"""Compare candidates on top-panel (ep,seat) and gauntlet (seed,opp) rows. argv: base top.jsonl g.jsonl [g2.jsonl]"""
import sys, json, collections, statistics as S
base = sys.argv[1]
def rep(R, tag):
    for c in sorted({c for v in R.values() for c in v} - {base}):
        d = [(v[base], v[c]) for v in R.values() if c in v and base in v]
        if not d: continue
        m = [b[0] - a[0] for a, b in d]
        print('%-4s %-16s n %4d  d_margin %+7.0f (2se %5.0f)  d_own %+7.0f  wins %3d vs base %3d  LW %d WL %d' % (
            tag, c, len(d), S.mean(m), 2 * S.pstdev(m) / len(d) ** .5, S.mean(b[1] - a[1] for a, b in d),
            sum(b[0] > 0 for a, b in d), sum(a[0] > 0 for a, b in d), sum(a[0] <= 0 < b[0] for a, b in d), sum(b[0] <= 0 < a[0] for a, b in d)))
T = collections.defaultdict(dict)
for l in open(sys.argv[2]):
    r = json.loads(l); T[(r['ep'], r['seat'])][r['cand']] = (r['ours'] - r['theirs'], r['ours'])
rep(T, 'top')
for f in sys.argv[3:]:
    G = collections.defaultdict(dict); H = collections.defaultdict(list)
    for l in open(f):
        r = json.loads(l)
        G[(r['seed'], r['p1'])][r['p0']] = (r['banks'][0] - r['banks'][1], r['banks'][0])
        H[(r['p0'], r['p1'])].append(r['banks'][0] - r['banks'][1])
    rep(G, 'g')
    print('head-to-head / per-opponent (cand vs opp: win%, mean margin, n):')
    for (a, b), v in sorted(H.items()):
        print('   %-18s vs %-16s %5.1f%% %+7.0f n %d' % (a, b, 100 * sum(x > 0 for x in v) / len(v), S.mean(v), len(v)))
