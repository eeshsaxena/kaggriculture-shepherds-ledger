"""List live episodes of our subs. argv: out.json sub:name ... ; prints per-sub summary by opp-rating band."""
import json, sys, time, urllib.request
URL = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"
def api(sub):
    for a in range(5):
        try:
            r = urllib.request.Request(URL, data=json.dumps({"submissionId": int(sub)}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(r, timeout=60).read())
        except Exception:
            time.sleep(3 * (a + 1))
    return None
rows = []
for arg in sys.argv[2:]:
    sub, name = arg.split(':'); sub = int(sub)
    d = api(sub) or {}
    for e in d.get('episodes') or []:
        ag = e.get('agents') or []
        if len(ag) != 2: continue
        me = [a for a in ag if a.get('submissionId') == sub]
        if len(me) != 1: continue
        me = me[0]; op = [a for a in ag if a is not me][0]
        rows.append(dict(ep=e['id'], sub=sub, name=name, seat=ag.index(me), me=me.get('reward'), op=op.get('reward'),
                         op_rating=op.get('updatedScore') or op.get('initialScore'), my_rating=me.get('updatedScore'),
                         op_sub=op.get('submissionId'), op_team=op.get('teamId'), end=e.get('endTime')))
json.dump(rows, open(sys.argv[1], 'w'))
for name in sorted(set(r['name'] for r in rows)):
    rr = sorted([r for r in rows if r['name'] == name and r['me'] is not None and not (r['me'] == 0 and r['op'] == 0)], key=lambda r: r['end'])
    print(name, len(rr), 'last', rr[-1]['end'][:16] if rr else '')
    for lo, hi in ((0, 2200), (2200, 2300), (2300, 2400), (2400, 2500), (2500, 9999)):
        b = [r for r in rr if lo <= (r['op_rating'] or 0) < hi]
        if b:
            w = sum(1 for r in b if r['me'] > r['op'])
            print('  op %4d-%4d  %2d/%2d  mean margin %+6.0f' % (lo, hi, w, len(b), sum(r['me'] - r['op'] for r in b) / len(b)))
