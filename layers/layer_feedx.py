


# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena, own implementation. FEEDX: skip end-game FEEDs that can no longer pay, outermost layer
# (research workflow wf_d90826fa-fa1, top_tapes lens + verifier). Engine: an animal produces overnight whenever
# (next_day - placed_day - first_yield_day) >= 0 and divisible by its interval, fed or not; feeding only prevents the
# escape at 2 consecutive unfed days (and banks the care bonus). _r85_feed never skips a FEED when consecutive_unfed
# is 1, so on days 27-28 we feed sheep that will never produce again (~2.3 feeds per game in live replays).
# RULE (day = step // 24 in [_FEEDX_FIRST_DAY, 28]): for each unit whose command is exactly ['FEED'], look at the tile
# under it (FEED acts on the unit's tile); rewrite to ['PASS'] only if the tile holds an animal, fed_today is False,
# its yield_units == 0 (an escape cannot destroy stock) and no production night q with day <= q <= 28 exists
# (q + 1 - placed_day - first >= 0 and divisible by interval, _R88_ANIMAL_DAYS). The wheat stays in the unit's
# inventory and reaches the shed at day end. Market orders untouched. Any exception -> parent action.
# ---------------------------------------------------------------------------
_FEEDX_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_FEEDX_ON = True
_FEEDX_FIRST_DAY = 26
_FEEDX_REPORT = dict(fires=0, by_animal={}, errors=0)


def _feedx_produces_by_28(tile, day):
    first, interval = _R88_ANIMAL_DAYS[tile['animal']]
    placed = int(tile.get('placed_day', 0))
    for q in range(day, 29):
        k = q + 1 - placed - first
        if k >= 0 and k % interval == 0:
            return True
    return False


def feedx_agent(observation, configuration=None):
    action = _FEEDX_PARENT[0](observation, configuration)
    try:
        step = int(observation['step']); day = step // 24
        if step == 0:
            _FEEDX_REPORT.update(fires=0, by_animal={}, errors=0)
        if not _FEEDX_ON or not isinstance(action, dict) or not _FEEDX_FIRST_DAY <= day <= 28:
            return action
        p = int(observation['player'])
        farm = observation['farms'][p]
        positions = [farm['farmer']] + list(farm.get('hands') or [])
        units = [action.get('farmer') or ['PASS']] + list(action.get('hands') or [])
        out = None
        for i, cmd in enumerate(units):
            if i >= len(positions) or not isinstance(cmd, (list, tuple)) or list(cmd) != ['FEED']:
                continue
            pos = positions[i]
            tile = farm['tiles'][int(pos[1])][int(pos[0])]
            if not isinstance(tile, dict) or tile.get('animal') not in ('GOOSE', 'COW', 'SHEEP'):
                continue
            if tile.get('fed_today') or int(tile.get('yield_units', 0)) != 0:
                continue
            if _feedx_produces_by_28(tile, day):
                continue
            if out is None:
                out = [list(u) if isinstance(u, (list, tuple)) else u for u in units]
            out[i] = ['PASS']
            _FEEDX_REPORT['fires'] += 1
            a = tile['animal']
            _FEEDX_REPORT['by_animal'][a] = _FEEDX_REPORT['by_animal'].get(a, 0) + 1
        if out is None:
            return action
        result = dict(action)
        result['farmer'] = out[0]
        result['hands'] = out[1:]
        return result
    except Exception:
        _FEEDX_REPORT['errors'] += 1
        return action


feedx_agent.telemetry = _FEEDX_REPORT
