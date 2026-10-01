"""Replay ONE pinned panel game exactly like the screen/confirm harness and save the full step log.
usage: PYTHONHASHSEED=0 ~/kaggri/venv/bin/python wf4/trace_one.py <compact_dir> <ep> <seat> <cand.py> <out.json.gz>
  compact_dir: compact_akmr | compact_top6x | compact_agi | compact_top5 (in ~/kaggri/beat/v92x)
  Candidate plays <seat>; the other seat replays its recorded tape; shops + rival weeds pinned (same as top_eval_det*).
Output (gzip json): {'ep','seat','cand','rewards':[r0,r1], 'steps':[ [ {'action':..,'observation':..,'reward':..,'status':..} x2 ] x 721 ]}
Also exposes run_game(compact_path, seat, cand_path) -> (env, rec, agent) for in-process use; agent.__globals__ is the stack module namespace, so agent.__globals__["_FEEDX_REPORT"] etc. give every layer telemetry (import sys; sys.path.insert(0, '~/kaggri/beat/v92x/wf4'))."""
import sys, os, json, gzip, io, contextlib
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import top_eval_detK1 as T


def run_game(path, seat, cp):
    import time as _tm
    _clk = [0.0]
    def _fake():
        _clk[0] += 5e-3
        return _clk[0]
    _tm.perf_counter = _fake
    rec = json.load(open(path))
    import kaggle_environments as ke
    from kaggle_environments.agent import get_last_callable
    o = 1 - seat
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        T.install(); T._PIN.clear()
        wd = {}
        for d, x, y in rec['weeds'][str(o)] if isinstance(rec['weeds'], dict) and str(o) in rec['weeds'] else rec['weeds'][o]:
            wd.setdefault(d, []).append((d, x, y))
        T._PIN.update(rival=o, weeds=wd, shops=rec['shops_by_day'], day=-1)
        tape_o = rec['tapes'][o]
        ag = [None, None]
        ag[seat] = get_last_callable(open(cp, encoding='utf-8').read(), path=cp)
        ag[o] = lambda obs, cfg=None: tape_o[obs['step']] if obs['step'] < len(tape_o) else {}
        env = ke.make('kaggriculture', configuration={'seed': rec['seed']}); env.run(ag)
        T._PIN.clear()
    return env, rec, ag[seat]


if __name__ == '__main__':
    cdir, ep, seat, cp, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
    env, rec, agent = run_game(os.path.join(HERE, cdir, 'o_%d.json' % ep), seat, cp)
    steps = [[{k: (dict(s[k]) if isinstance(s[k], dict) else s[k]) for k in ('action', 'observation', 'reward', 'status') if k in s}
              for s in st] for st in env.steps]
    json.dump({'ep': ep, 'seat': seat, 'cand': os.path.basename(cp), 'names': rec['names'],
               'rewards': [env.steps[-1][k].get('reward') for k in (0, 1)], 'steps': steps},
              gzip.open(out, 'wt'), default=lambda x: dict(x) if hasattr(x, 'keys') else str(x))
    print('rewards', [env.steps[-1][k].get('reward') for k in (0, 1)], 'saved', out)
