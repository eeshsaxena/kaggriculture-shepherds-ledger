"""Twin replay compare by win flips. argv: re.jsonl base [sub_filter]"""
import sys, json, collections, statistics as S
R = collections.defaultdict(dict); subs = {}
for l in open(sys.argv[1]):
    r = json.loads(l)
    if 'ours' in r: R[(r['ep'], r.get('seat'))][r['cand']] = r['ours'] - r['theirs']; subs[(r['ep'], r.get('seat'))] = r.get('sub')
base = sys.argv[2]; filt = set(int(x) for x in sys.argv[3].split(',')) if len(sys.argv) > 3 else None
for c in sorted({c for v in R.values() for c in v} - {base}):
    d = [(v[base], v[c], k) for k, v in R.items() if c in v and base in v and (filt is None or subs[k] in filt)]
    if not d: continue
    lw = [k[0] for a, b, k in d if a <= 0 < b]; wl = [k[0] for a, b, k in d if b <= 0 < a]
    print('%-14s n %4d changed %4d margin %+6.0f 2se %5.0f wins %d vs %d LW %d WL %d' % (c, len(d), sum(a != b for a, b, k in d), S.mean(b - a for a, b, k in d), 2 * S.pstdev([b - a for a, b, k in d]) / len(d) ** .5, sum(b > 0 for a, b, k in d), sum(a > 0 for a, b, k in d), len(lw), len(wl)), 'LW', lw[:8], 'WL', wl[:8])
