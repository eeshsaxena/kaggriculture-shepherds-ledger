


# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena, own implementation. FAMTW: family-fork TWIN reclassification at step 47, outermost layer
# (workflow wf_c996865b-507, lens nt_close + two verifiers). D1 flags a rival non-twin when its hand count differs from
# ours at steps 23/47 or in the per-day max over days 0-1. About 5% of live games are public-family forks that differ
# from us ONLY by one hire on day 0 or 1: same quadrants, same placed animals, same tile census, same routes. D1 marks
# them non-twin, which switches off every twin-validated layer (TWK knobs, V231T, H0S/H0F, W709, D7S, VL1...).
# RULE: at steps 23 and 47 (before the parent call) compare the two farms: tile census mismatch (Counter of
#   (kind, crop, animal) per tile, sum |diff| / 2) <= _FAMTW_MAX_CENSUS_MISMATCH, sorted unlocked quadrants equal,
#   placed-animal census equal, |hands own - hands rival| <= _FAMTW_MAX_HAND_DIFF; and the per-day max hand counts of
#   days 0 and 1 differ by <= _FAMTW_MAX_HAND_DIFF. After the parent call at step 47 (D1 and D1b have latched), if all
#   hold and _NT_D1[p] is True, set _NT_D1[p] = False for the rest of the game. The layer never edits an action; it is
#   byte-identical whenever it does not reclassify (true twins are never touched: their flag is already False).
# Any exception -> no reclassification, parent action returned unchanged.
# ---------------------------------------------------------------------------
_FAMTW_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_FAMTW_ON = True
_FAMTW_MAX_CENSUS_MISMATCH = 1
_FAMTW_MAX_HAND_DIFF = 1
_FAMTW_STATE = {}
_FAMTW_REPORT = dict(checks=0, reclassified=0, why='', errors=0)


def _famtw_census(farm):
    c = {}
    for row in (farm.get('tiles') or []):
        for t in row:
            if isinstance(t, dict):
                k = (t.get('kind'), t.get('crop'), t.get('animal'))
            else:
                k = (t,)
            c[k] = c.get(k, 0) + 1
    return c


def _famtw_animals(farm):
    c = {}
    for row in (farm.get('tiles') or []):
        for t in row:
            if isinstance(t, dict) and 'animal' in t:
                c[t['animal']] = c.get(t['animal'], 0) + 1
    return c


def famtw_agent(observation, configuration=None):
    st = None; step = -1; p = 0
    try:
        step = int(observation['step']); p = int(observation['player'])
        st = _FAMTW_STATE.get(p)
        if st is None or step == 0 or step < st['step']:
            st = _FAMTW_STATE[p] = {'step': -1, 'ok': True, 'maxo': {}, 'maxr': {}, 'why': ''}
            if step == 0:
                _FAMTW_REPORT.update(checks=0, reclassified=0, why='')
        st['step'] = step
        if step <= 47:
            farms = observation['farms']; own = farms[p]; riv = farms[1 - p]
            oh = len(own.get('hands') or []); rh = len(riv.get('hands') or [])
            d = step // 24
            st['maxo'][d] = max(st['maxo'].get(d, 0), oh); st['maxr'][d] = max(st['maxr'].get(d, 0), rh)
            if step in (23, 47):
                _FAMTW_REPORT['checks'] += 1
                co = _famtw_census(own); cr = _famtw_census(riv)
                mism = sum(abs(co.get(k, 0) - cr.get(k, 0)) for k in set(co) | set(cr)) // 2
                qeq = sorted(own.get('unlocked_quadrants') or []) == sorted(riv.get('unlocked_quadrants') or [])
                aeq = _famtw_animals(own) == _famtw_animals(riv)
                if mism > _FAMTW_MAX_CENSUS_MISMATCH:
                    st['ok'] = False; st['why'] = 'census%d@%d' % (mism, step)
                elif not qeq:
                    st['ok'] = False; st['why'] = 'quads@%d' % step
                elif not aeq:
                    st['ok'] = False; st['why'] = 'animals@%d' % step
                elif abs(oh - rh) > _FAMTW_MAX_HAND_DIFF:
                    st['ok'] = False; st['why'] = 'hands@%d' % step
    except Exception:
        _FAMTW_REPORT['errors'] += 1
        if st is not None:
            st['ok'] = False; st['why'] = 'error'
    action = _FAMTW_PARENT[0](observation, configuration)
    try:
        if step == 47 and st is not None and _FAMTW_ON:
            nt = globals().get('_NT_D1')
            days_ok = all(abs(st['maxo'].get(d, 0) - st['maxr'].get(d, 0)) <= _FAMTW_MAX_HAND_DIFF for d in (0, 1))
            if isinstance(nt, dict) and nt.get(p) is True and st['ok'] and days_ok:
                nt[p] = False
                _FAMTW_REPORT['reclassified'] = 1
                _FAMTW_REPORT['why'] = 'reclassified'
            else:
                _FAMTW_REPORT['why'] = st['why'] or ('days' if not days_ok else ('twin' if not (isinstance(nt, dict) and nt.get(p)) else ''))
    except Exception:
        _FAMTW_REPORT['errors'] += 1
    return action


famtw_agent.telemetry = _FAMTW_REPORT
