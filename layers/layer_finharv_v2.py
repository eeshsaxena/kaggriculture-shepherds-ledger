


# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena, waste-audit synthesis (wf_560b0cb1-321). FINHARV v2: harvest a finished ongoing crop instead
# of watering it, outermost layer (after COWBANK, before OVERSKIP23).
# Engine: on the night of an ongoing crop's last production (production_count == max_yield) _daily_refresh_plants
# sets max_lifespan_step = (next_day + 1) * 24 and the tile never produces again (production_count > max_yield ->
# continue). WATER on an ongoing crop only sets watered_today (the yield bonus is one-time crops only). From
# max_lifespan_step _decay_plants removes one unit every 2 steps and turns the tile to WEED at 0, so an earlier HARVEST
# always collects at least what a later one would. Live (515 games FK..FN): 246 day-22 tomatoes rot in 46 games with
# one of our units standing on the tile doing WATER/PASS.
# RULE (step < _FINHARV_LAST_STEP): for each unit whose command is exactly ['WATER'] or ['PASS'], the tile under it is
# a PLANT of TOMATO/STRAWBERRY with max_lifespan_step >= 0 and yield_units > 0, and no other unit of ours HARVESTs that
# tile this step -> ['HARVEST'] (the unit does not move; market orders untouched).
# v2 changes vs pub2/layer_finharv.py: (a) never fires from step 672 on. Day 29 has no night auto-drop, so a lot moved
# to a unit with no DROP left is lost (4/515 live games); day-28 fires were all neutral (the tape harvests the same
# tile one step later) and only add route noise. (b) Hour-23 guard: the rewrite is kept only if the extra quote value
# ROOM23's exact projection destroys at tonight's drop is below the quote value harvested (0 measured cases).
# Any exception -> parent action.
# ---------------------------------------------------------------------------
_FINHARV_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_FINHARV_ON = True
_FINHARV_CROPS = ('TOMATO', 'STRAWBERRY')
_FINHARV_LAST_STEP = 672        # exclusive; 696 = verifier variant (keeps the neutral day-28 fires)
_FINHARV_REPORT = dict(fires=0, units=0, h23_reverts=0, errors=0, fire_log=[])


def _finharv_v(proj, prices):
    return float(sum(int(prices.get(x, 0) or 0) for x in proj['seq']))


def finharv_agent(observation, configuration=None):
    action = _FINHARV_PARENT[0](observation, configuration)
    try:
        step = int(observation['step'])
        if step == 0:
            _FINHARV_REPORT.update(fires=0, units=0, h23_reverts=0, errors=0, fire_log=[])
        if not _FINHARV_ON or not isinstance(action, dict) or step >= _FINHARV_LAST_STEP:
            return action
        p = int(observation['player'])
        farm = observation['farms'][p]
        tiles = farm['tiles']
        positions = [farm['farmer']] + list(farm.get('hands') or [])
        units = [action.get('farmer') or ['PASS']] + list(action.get('hands') or [])
        out = None
        taken = set()
        fired = []
        for i, cmd in enumerate(units):
            if i >= len(positions) or not isinstance(cmd, (list, tuple)) or list(cmd) not in (['WATER'], ['PASS']):
                continue
            x, y = int(positions[i][0]), int(positions[i][1])
            if (x, y) in taken:
                continue
            tile = tiles[y][x]
            if not isinstance(tile, dict) or tile.get('kind') != 'PLANT' or tile.get('crop') not in _FINHARV_CROPS:
                continue
            if int(tile.get('max_lifespan_step', -1)) < 0 or int(tile.get('yield_units', 0)) <= 0:
                continue
            if any(j != i and j < len(positions) and int(positions[j][0]) == x and int(positions[j][1]) == y
                   and isinstance(units[j], (list, tuple)) and units[j] and units[j][0] == 'HARVEST'
                   for j in range(len(units))):
                continue
            if out is None:
                out = [list(u) if isinstance(u, (list, tuple)) else u for u in units]
            out[i] = ['HARVEST']
            taken.add((x, y))
            fired.append((i, x, y, int(tile.get('yield_units', 0))))
        if out is None:
            return action
        result = dict(action)
        result['farmer'] = out[0]
        result['hands'] = out[1:]
        if step % 24 == 23:
            base = _rm_project(observation, action, p)
            new = _rm_project(observation, result, p)
            prices = observation['market']['prices']
            gain = float(sum(f[3] * int(prices.get(tiles[f[2]][f[1]]['crop'], 0) or 0) for f in fired))
            if base is None or new is None or _finharv_v(new, prices) - _finharv_v(base, prices) >= gain:
                _FINHARV_REPORT['h23_reverts'] += 1
                return action
        _FINHARV_REPORT['fires'] += len(fired)
        _FINHARV_REPORT['units'] += sum(f[3] for f in fired)
        _FINHARV_REPORT['fire_log'].extend((step,) + f for f in fired)
        return result
    except Exception:
        _FINHARV_REPORT['errors'] += 1
        return action


finharv_agent.telemetry = _FINHARV_REPORT
