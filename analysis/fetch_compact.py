"""Download live replays (box) and compact them to seed + both action tapes. argv: live_all.json nthreads"""
import sys, json, os, urllib.request, time
from multiprocessing.pool import ThreadPool
rows = json.load(open(sys.argv[1])); os.makedirs('replays', exist_ok=True); os.makedirs('compact', exist_ok=True)
def one(r):
    ep = r['ep']; raw = 'replays/%d.json' % ep; out = 'compact/o_%d.json' % ep
    if os.path.exists(out): return 'skip'
    err = ''
    for k in range(4):
        try:
            if not os.path.exists(raw) or os.path.getsize(raw) < 1000:
                req = urllib.request.Request("https://www.kaggle.com/competitions/episodes/%d/replay.json" % ep, headers={"User-Agent": "Mozilla/5.0"})
                data = urllib.request.urlopen(req, timeout=300).read()
                open(raw + '.part', 'wb').write(data); os.replace(raw + '.part', raw)
            rep = json.load(open(raw)); st = rep['steps']
            tn = rep['info'].get('TeamNames'); names = json.loads(tn) if isinstance(tn, str) else tn
            tape = lambda s: [(st[i][s].get('action') if isinstance(st[i][s].get('action'), dict) else {}) for i in range(1, len(st))]
            json.dump({'ep': ep, 'sub': r['sub'], 'seat': r['seat'], 'seed': rep['info'].get('seed'), 'names': list(names or []),
                       'rewards': [st[-1][k2].get('reward') for k2 in (0, 1)], 'tapes': [tape(0), tape(1)]}, open(out, 'w'))
            return 'ok'
        except Exception as e:
            err = repr(e)[:120]; time.sleep(5)
    return 'fail ' + err
if __name__ == '__main__':
    with ThreadPool(int(sys.argv[2])) as p:
        for i, res in enumerate(p.imap_unordered(one, rows)):
            if i % 20 == 0 or not res.startswith(('ok', 'skip')): print(i, res, time.strftime('%H:%M:%S'), flush=True)
    print('DONE', flush=True)
