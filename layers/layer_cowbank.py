


# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena. From the waste-audit herd lens draft (workflow wf_560b0cb1-321); box-tested before any use.
# COWBANK: skip pre-production cow FEEDs whose care bank can only be clipped by max_held, outermost layer (after FEEDX).
# Engine (_daily_refresh_animals): a cow's first production night is the end of day placed_day + 7; there
# yield = min(6, 0 + 1 + pending_care_bonus) when fed that day, so at most 5 banked cares can ever pay. The 7
# pre-production days placed..placed+6 can bank up to 7, and banks beyond 5 are clipped. Survival only needs no two
# consecutive unfed day ends.
# RULE (day = step // 24 in [_COWBANK_FIRST_DAY, _COWBANK_LAST_DAY]): for each tile FEEDed by exactly one unit in the
# final action (command exactly ['FEED']): the tile holds a COW with fed_today False, consecutive_unfed == 0,
# yield_units == 0, day <= placed_day + 6 and placed_day + 7 <= 28; the raw route tape FEEDs the tile tomorrow
# (_r86_next_feed); and pending_care_bonus + (number of days e in [day+1, placed_day+6] on which the raw tape both FEEDs
# (wheat model) and CAREs the tile) >= 5. Then that unit's command becomes ['PASS'] (its wheat drops into the shed at day
# end). Market orders untouched. Any exception -> parent action.
# ---------------------------------------------------------------------------
_COWBANK_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_COWBANK_ON = True
_COWBANK_FIRST_DAY = 6          # route is fixed from step 144; tomorrow's plan is reliable from day 6
_COWBANK_LAST_DAY = 25          # FEEDX owns days 26-28
_COWBANK_NEED = 5               # COW max_held 6 minus the base unit
_COWBANK_REPORT = dict(fires=0, errors=0, fire_log=[])
_COWBANK_PLAN = {}


def _cowbank_banks(route, day):
    """Tiles the raw tape both FEEDs (wheat model as _r86_next_feed) and CAREs on `day`."""
    key = (route, day)
    if key not in _COWBANK_PLAN:
        positions = [(4, 4)]; wheat = [0]; access = ((4, 4), (5, 4), (4, 5), (5, 5)); feeds = set(); cares = set()
        for hour in range(24):
            t = day * 24 + hour
            if t >= 719:
                break
            a = _IMPL.chassis.routes[route][t]
            commands = [a.get('farmer') or ['PASS'], *(a.get('hands') or [])]
            for actor, command in enumerate(commands[:len(positions)]):
                if not command:
                    continue
                pos = positions[actor]; op = command[0]
                if op in MOVES:
                    dx, dy = MOVES[op]; positions[actor] = (max(0, min(9, pos[0] + dx)), max(0, min(9, pos[1] + dy)))
                elif command[:2] == ['PICKUP', 'WHEAT'] and pos in access:
                    wheat[actor] += max(0, int(command[2]) if len(command) > 2 else 1)
                elif op == 'FEED' and wheat[actor] > 0:
                    wheat[actor] -= 1; feeds.add(pos)
                elif op == 'CARE':
                    cares.add(pos)
                elif op == 'DROP' and pos in access:
                    wheat[actor] = 0
                elif command[:2] == ['PLACE', 'WHEAT'] and pos in access:
                    wheat[actor] = max(0, wheat[actor] - max(0, int(command[2]) if len(command) > 2 else 1))
            for order in a.get('market', []):
                if order and order[0] == 'HIRE':
                    chosen = min(access, key=lambda q: (positions.count(q), access.index(q)))
                    positions.append(chosen); wheat.append(0)
        _COWBANK_PLAN[key] = frozenset(feeds & cares)
    return _COWBANK_PLAN[key]


def cowbank_agent(observation, configuration=None):
    action = _COWBANK_PARENT[0](observation, configuration)
    try:
        step = int(observation['step']); day = step // 24
        if step == 0:
            _COWBANK_REPORT.update(fires=0, errors=0, fire_log=[])
        if not _COWBANK_ON or not isinstance(action, dict) or not _COWBANK_FIRST_DAY <= day <= _COWBANK_LAST_DAY:
            return action
        p = int(observation['player'])
        farm = observation['farms'][p]
        positions = [farm['farmer']] + list(farm.get('hands') or [])
        units = [action.get('farmer') or ['PASS']] + list(action.get('hands') or [])
        feeders = {}
        for i, cmd in enumerate(units):
            if i < len(positions) and isinstance(cmd, (list, tuple)) and list(cmd) == ['FEED']:
                feeders.setdefault((int(positions[i][0]), int(positions[i][1])), []).append(i)
        if not feeders:
            return action
        route = _IMPL.chassis.players[p]['route']
        out = None
        for pos, idx in feeders.items():
            if len(idx) != 1:
                continue
            tile = farm['tiles'][pos[1]][pos[0]]
            if not isinstance(tile, dict) or tile.get('animal') != 'COW':
                continue
            if tile.get('fed_today') or int(tile.get('consecutive_unfed', 0)) != 0 or int(tile.get('yield_units', 0)) != 0:
                continue
            placed = int(tile.get('placed_day', 0)); last_pre = placed + 6
            if day > last_pre or placed + 7 > 28:
                continue
            if not _r86_next_feed(observation, list(pos)):
                continue
            banks = max(0, int(tile.get('pending_care_bonus', 0)))
            for e in range(day + 1, last_pre + 1):
                if pos in _cowbank_banks(2 if e >= 27 else route, e):
                    banks += 1
            if banks < _COWBANK_NEED:
                continue
            if out is None:
                out = [list(u) if isinstance(u, (list, tuple)) else u for u in units]
            out[idx[0]] = ['PASS']
            _COWBANK_REPORT['fires'] += 1
            _COWBANK_REPORT['fire_log'].append((step, pos, placed, banks))
        if out is None:
            return action
        result = dict(action)
        result['farmer'] = out[0]
        result['hands'] = out[1:]
        return result
    except Exception:
        _COWBANK_REPORT['errors'] += 1
        return action


cowbank_agent.telemetry = _COWBANK_REPORT
