


# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena, waste-audit synthesis (wf_560b0cb1-321). OVERSKIP23 v2: at hour 23, when the day-end
# auto-drop will destroy cargo that ROOM23 cannot rescue (cargo alone > free room; live 489 nights in 336/515 games, all
# with the shed empty after the hour-23 market), turn hour-23 unit actions that ADD cargo into PASS:
#   C  COLLECT_FERTILIZER (forfeits 1 fertilizer; fertilizer_available is reset every night, never banked)
#   O  HARVEST of TOMATO/STRAWBERRY with max_lifespan_step < 0 and yield + tonight's production <= 4 (lot waits)
#   G  HARVEST of a GOOSE with yield + 1 + pending_care_bonus <= 4 (lot waits on the coop)
#   P  HARVEST of WHEAT/CARROT/MELON on day >= _OS_P_DAY (forfeited: nothing planted now can mature)
# Units are tried last to first (the drop destroys the tail); each skip is kept only if ROOM23's exact projection
# (_rm_project: unit actions -> market on the shed -> day-end drop) shows the destroyed quote value falling by more
# than _OS_MARGIN plus the quote value the skip forfeits. COW/SHEEP are never skipped.
# v2 guards vs pub2/layer_overskip.py:
#   (1) O: the tile must survive tonight: watered_today, or another unit of ours WATERs it this step, or
#       consecutive_unwatered == 0 (else WEED tonight with the lot). And tonight must not be its final production
#       unless FINHARV is in the stack and still active tomorrow (a final production starts decay at (day + 2) * 24).
#   (2) G: the goose must not escape tonight: fed_today, or another unit of ours FEEDs it this step while carrying
#       WHEAT, or consecutive_unfed == 0.
#   (3) Need: a C skip (FERTILIZER) or a P skip of WHEAT is kept only if the projected post-drop shed stock of that
#       item >= min(PICKUP need on the tape in the next 24 steps, base post-drop stock).
# Market orders untouched. Any exception -> parent action.
# ---------------------------------------------------------------------------
_OS_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_OS_ON = True
_OS_MARGIN = 100.0
_OS_P_DAY = 27
_OS_KINDS = ('C', 'O', 'G', 'P')   # ('C', 'P') = zero-chain core
_OS_ONG = {'TOMATO': (8, 1, 4), 'STRAWBERRY': (10, 2, 4)}          # first_yield_day, interval, max_yield
_OS_ONE = {'WHEAT': 2, 'CARROT': 2, 'MELON': 10}                  # first_yield_day
_OS_REPORT = dict(fires=0, skips={}, saved_units=0, guard_blocks={}, errors=0, fire_log=[])


def _os_value(seq, prices):
    return float(sum(int(prices.get(x, 0) or 0) for x in seq))


def _os_block(k):
    _OS_REPORT['guard_blocks'][k] = _OS_REPORT['guard_blocks'].get(k, 0) + 1


def _os_candidate(tile, i, units, positions, invs, day):
    """-> (kind, forfeited item, forfeited units) or None."""
    if not isinstance(tile, dict):
        return None
    cmd = units[i]; op = cmd[0]
    x, y = int(positions[i][0]), int(positions[i][1])

    def other(opname, need_item=None):
        for j, c in enumerate(units):
            if j == i or j >= len(positions) or not isinstance(c, list) or not c or c[0] != opname:
                continue
            if int(positions[j][0]) != x or int(positions[j][1]) != y:
                continue
            if need_item and int((invs[j] if j < len(invs) else {}).get(need_item, 0) or 0) <= 0:
                continue
            return True
        return False

    if op == 'COLLECT_FERTILIZER' and 'animal' in tile and tile.get('fertilizer_available'):
        return ('C', 'FERTILIZER', 1)
    if op != 'HARVEST':
        return None
    yu = int(tile.get('yield_units', 0) or 0)
    if yu <= 0:
        return None
    if tile.get('animal') == 'GOOSE':
        placed = int(tile.get('placed_day', 0))
        prod = 1 + int(tile.get('pending_care_bonus', 0) or 0) if day + 1 - placed - 4 >= 0 else 0
        if yu + prod > 4:
            return None
        if not (tile.get('fed_today') or int(tile.get('consecutive_unfed', 0) or 0) == 0
                or other('FEED', 'WHEAT')):
            _os_block('G_escape')
            return None
        return ('G', None, 0)
    if tile.get('kind') != 'PLANT':
        return None
    crop = tile.get('crop'); planted = int(tile.get('planted_day', 0))
    if crop in _OS_ONG:
        first, interval, mx = _OS_ONG[crop]
        if day - planted < first or int(tile.get('max_lifespan_step', -1)) >= 0:
            return None
        dsf = day + 1 - planted - first
        prod = 0; final = False
        if dsf >= 0 and dsf % interval == 0 and dsf // interval + 1 <= mx:
            prod = 2 if int(tile.get('fertilized_until_day', -1)) >= day else 1
            final = dsf // interval + 1 == mx
        if yu + prod > mx:
            return None
        if not (tile.get('watered_today') or int(tile.get('consecutive_unwatered', 0) or 0) == 0 or other('WATER')):
            _os_block('O_weed')
            return None
        if final and not ('finharv_agent' in globals() and globals().get('_FINHARV_ON')
                          and (day + 1) * 24 < int(globals().get('_FINHARV_LAST_STEP', 696))):
            _os_block('O_final')
            return None
        return ('O', None, 0)
    if crop in _OS_ONE and day >= _OS_P_DAY and day - planted >= _OS_ONE[crop]:
        return ('P', crop, yu)
    return None


def overskip_agent(observation, configuration=None):
    action = _OS_PARENT[0](observation, configuration)
    try:
        step = int(observation['step']); day = step // 24
        if step == 0:
            _OS_REPORT.update(fires=0, skips={}, saved_units=0, guard_blocks={}, errors=0, fire_log=[])
        if not _OS_ON or not isinstance(action, dict) or step % 24 != 23 or step >= 718:
            return action
        p = int(observation['player'])
        base = _rm_project(observation, action, p)
        if base is None or not base['seq']:
            return action
        prices = observation['market']['prices']
        farm = observation['farms'][p]
        invs = list((observation.get('private') or {}).get('inventories') or [])
        positions = [farm['farmer']] + list(farm.get('hands') or [])
        units = [list(u) if isinstance(u, (list, tuple)) else u for u in
                 [action.get('farmer') or ['PASS']] + list(action.get('hands') or [])]
        need = None
        cur = dict(action); cur_seq = base['seq']; cur_v = _os_value(cur_seq, prices)
        n0 = len(cur_seq); skipped = []
        for i in range(min(len(units), len(positions)) - 1, -1, -1):
            if not cur_seq:
                break
            cmd = units[i]
            if not isinstance(cmd, list) or not cmd:
                continue
            x, y = int(positions[i][0]), int(positions[i][1])
            c = _os_candidate(farm['tiles'][y][x], i, units, positions, invs, day)
            if c is None or c[0] not in _OS_KINDS:
                continue
            trial_units = list(units); trial_units[i] = ['PASS']
            trial = dict(cur); trial['farmer'] = trial_units[0]; trial['hands'] = trial_units[1:]
            pr = _rm_project(observation, trial, p)
            if pr is None:
                continue
            own = c[2] * float(int(prices.get(c[1], 0) or 0)) if c[1] else 0.0
            v = _os_value(pr['seq'], prices)
            if cur_v - v - own <= _OS_MARGIN:
                continue
            if c[1] in ('FERTILIZER', 'WHEAT'):
                if need is None:
                    need = _rm_need(p, step)
                floor = min(int(need.get(c[1], 0)), int(base['post'].get(c[1], 0)))
                if int(pr['post'].get(c[1], 0)) < floor:
                    _os_block('need_' + c[1])
                    continue
            units = trial_units; cur = trial; cur_seq = pr['seq']; cur_v = v
            skipped.append(c[0])
        if not skipped:
            return action
        _OS_REPORT['fires'] += 1
        _OS_REPORT['saved_units'] += n0 - len(cur_seq)
        _OS_REPORT['fire_log'].append((step, tuple(skipped), n0 - len(cur_seq)))
        for k in skipped:
            _OS_REPORT['skips'][k] = _OS_REPORT['skips'].get(k, 0) + 1
        return cur
    except Exception:
        _OS_REPORT['errors'] += 1
        return action


overskip_agent.telemetry = _OS_REPORT
