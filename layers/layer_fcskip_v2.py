



# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena, own implementation. FCSKIP v2 (W5 fert lens; replaces layer_w5fert.py v1): skip a
# COLLECT_FERTILIZER whose unit will only displace higher-value cargo at the day-end drop.
# Measured on 12 FOB3n panel games (wf5fert/fert_trace.py, engine-instrumented): fertilizer itself is a profit centre
# (~370 collected, ~110 bought, ~340 sold for $13-24k, ~140 applied for +250 yield units per game; buy->sell round
# trips lose $1-36/game, 0 units left unsold). The recurring leak is the day-end drop on days 24-25: the hour-21
# strawberry harvest (16-19 units) lifts the carried cargo to 99-109 with an EMPTY shed (room_guard has nothing to
# sell), the hour-22 COLLECT and the hour-23 HARVEST add 3-4 more and the drop destroys the tail (3-5 STRAWBERRY at
# $194 in 3/12 games, 2-6 EGG/MILK + 2-4 FERTILIZER in 8/12) while 13-19 fertilizer units ($7-55) ride in the cargo.
# OVERSKIP23 v2 only acts at hour 23 (where the units WATER), so the day's earlier collects are untouched.
# RULE A (v1, hours 18-22): T = shed + carried + this step's HARVEST yields + collects - FEED/FERTILIZE. If
#   T + _FC_TAIL > cap and the shed holds <= _FC_SHED_MAX, up to (T + _FC_TAIL - cap) collects become PASS.
# RULE B (v2, hours _FC2_H0..22): replay the rest of today on our route tape (_rm_tape(p, t): the chassis' chosen
#   route, positions simulated from the tape's moves, HARVEST = projected yield_units of the target tile (tape WATERs
#   add the window bonus to wheat/carrot/melon, +2 when fertilized, capped), once per tile,
#   PLANT harvest only at age >= first_yield_day, COLLECT once per animal tile with fertilizer_available, FEED /
#   FERTILIZE / PLACE-animal consume from the unit's projected inventory, PICKUP / PLACE / DROP move stock between
#   the shed and the unit at the shed-access tiles). destroyed = projected cargo + unsellable shed stock (animals) -
#   cap. Skip now only the part later tape collects (hours <= 22) cannot absorb: k = destroyed - later collects.
# Both: last unit first, only while the fertilizer quote + _FC_MARGIN < the cheapest product carried by the last two
# loaded units (the drop destroys the tail of the inventory list; rule B uses the projected end-of-day inventories),
# and only while the post-drop fertilizer stock stays >= the tape's next-day PICKUP need (_rm_need).
# fertilizer_available is reset every night, so a skipped collect forfeits exactly one unit (never banked).
# Market orders untouched. Any exception -> parent action.
# ---------------------------------------------------------------------------
_FC_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_FC_ON = True
_FC_H0 = 18
_FC2_H0 = 14
_FC_TAIL = 3
_FC_MARGIN = 10.0
_FC_SHED_MAX = 10
_FC2_PAD = 1          # layer-added hands are not on the tape; a false positive costs one fertilizer unit
_FC2_MAXD = 12        # a projected overflow above this (or cargo already far over capacity) means the tape sells later: distrust
_FC2_TNOW_SLACK = 10
_FC2_MAX_MISMATCH = 2 # tape/actual command mismatches among tape units this step above this = unit index shift: distrust
_FC_ANIMALS = ('GOOSE', 'COW', 'SHEEP')
_FC_FIRST = {'WHEAT': 2, 'CARROT': 2, 'TOMATO': 8, 'STRAWBERRY': 10, 'MELON': 10}
_FC_ONE = {'WHEAT': (4, 6), 'CARROT': (3, 4), 'MELON': (12, 6)}   # max_yield_day, max_yield (WATER adds yield in the window)
_FC_REPORT = dict(fires=0, skips=0, skips_a=0, skips_b=0, blocks={}, errors=0, fire_log=[])


def _fc_block(k):
    _FC_REPORT['blocks'][k] = _FC_REPORT['blocks'].get(k, 0) + 1


def _fc_int(v, d=0):
    try:
        return int(v)
    except Exception:
        return d


def _fc_tail_price(invs, prices):
    loaded = [inv for inv in invs if any(_fc_int(v) > 0 for v in inv.values())]
    items = set()
    for inv in loaded[-2:]:
        for k, v in inv.items():
            if _fc_int(v) > 0 and k != 'FERTILIZER':
                items.add(k)
    if not items:
        return None, items
    return min(float(_fc_int(prices.get(k, 0))) for k in items), items


def _fc_project(observation, p, step, tiles, positions, units, invs, shed, cap):
    """Replay the rest of today on the tape. -> (destroyed, later_collects, tail_price, tail_items, cargo_end)."""
    day = step // 24
    B = len(tiles); h = B // 2
    access = {(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)}
    pos = [[_fc_int(q[0]), _fc_int(q[1])] for q in positions]
    inv = [dict((k, max(0, _fc_int(v))) for k, v in (invs[i] if i < len(invs) else {}).items()) for i in range(len(pos))]
    sh = dict((k, max(0, _fc_int(v))) for k, v in shed.items())
    harvested = set(); collected = set(); fed = set(); watered = set(); yld = {}

    def tile_yield(x, y, tile):
        if (x, y) not in yld:
            yld[(x, y)] = max(0, _fc_int(tile.get('yield_units', 0)))
        return yld[(x, y)]

    def add(d, k, n):
        if n > 0:
            d[k] = d.get(k, 0) + n

    def take(d, k, n):
        have = d.get(k, 0)
        n = min(n, have)
        if n > 0:
            d[k] = have - n
            if d[k] <= 0:
                del d[k]
        return n

    def shed_room():
        return max(0, cap - sum(sh.values()))

    def apply(i, c, current):
        if not isinstance(c, list) or not c:
            return
        op = c[0]
        x, y = pos[i]
        if op in ('NORTH', 'SOUTH', 'EAST', 'WEST'):
            dx, dy = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}[op]
            if 0 <= x + dx < B and 0 <= y + dy < B:
                pos[i] = [x + dx, y + dy]
            return
        tile = tiles[y][x] if 0 <= y < B and 0 <= x < len(tiles[y]) else None
        if op == 'HARVEST':
            if not isinstance(tile, dict) or (x, y) in harvested:
                return
            yu = tile_yield(x, y, tile)
            if yu <= 0:
                return
            if tile.get('kind') == 'PLANT':
                crop = tile.get('crop')
                if day - _fc_int(tile.get('planted_day', 0)) < _FC_FIRST.get(crop, 0):
                    return
                item = crop
            elif 'animal' in tile:
                item = {'GOOSE': 'EGG', 'COW': 'MILK', 'SHEEP': 'WOOL'}.get(tile.get('animal'))
            else:
                return
            harvested.add((x, y)); add(inv[i], item, yu)
        elif op == 'WATER':
            if not (isinstance(tile, dict) and tile.get('kind') == 'PLANT') or tile.get('watered_today') or (x, y) in watered:
                return
            watered.add((x, y))
            crop = tile.get('crop')
            if crop in _FC_ONE and (x, y) not in harvested:
                myd, mx = _FC_ONE[crop]
                age = day - _fc_int(tile.get('planted_day', 0))
                if (myd + 1) // 2 <= age <= myd:
                    bonus = 2 if _fc_int(tile.get('fertilized_until_day', -1)) >= day else 1
                    yld[(x, y)] = min(mx, tile_yield(x, y, tile) + bonus)
        elif op == 'COLLECT_FERTILIZER':
            if isinstance(tile, dict) and 'animal' in tile and tile.get('fertilizer_available') and (x, y) not in collected:
                collected.add((x, y)); add(inv[i], 'FERTILIZER', 1)
        elif op == 'FEED':
            if isinstance(tile, dict) and 'animal' in tile and not tile.get('fed_today') and (x, y) not in fed:
                if take(inv[i], 'WHEAT', 1):
                    fed.add((x, y))
        elif op == 'FERTILIZE':
            if isinstance(tile, dict) and tile.get('kind') == 'PLANT':
                take(inv[i], 'FERTILIZER', 1)
        elif op == 'PICKUP':
            if (x, y) in access and len(c) >= 2:
                n = _fc_int(c[2], 1) if len(c) >= 3 else 1
                got = take(sh, c[1], max(0, n)); add(inv[i], c[1], got)
        elif op == 'PLACE':
            if len(c) < 2:
                return
            item = c[1]
            if item in _FC_ANIMALS and isinstance(tile, dict) and 'animal' not in tile and tile.get('kind') in ('COOP', 'PASTURE'):
                take(inv[i], item, 1)
            elif (x, y) in access:
                n = _fc_int(c[2], 1) if len(c) >= 3 else 1
                n = min(max(0, n), inv[i].get(item, 0), shed_room())
                take(inv[i], item, n); add(sh, item, n)
        elif op == 'DROP':
            if (x, y) in access:
                for k in list(inv[i].keys()):
                    n = min(inv[i][k], shed_room())
                    take(inv[i], k, n); add(sh, k, n)

    # this step: the parent's real action
    for i in range(min(len(units), len(pos))):
        apply(i, units[i], True)
    later_collects = 0
    end = day * 24 + 23
    for t in range(step + 1, end + 1):
        a = _rm_tape(p, t)
        if not isinstance(a, dict):
            continue
        cmds = [a.get('farmer') or ['PASS']] + list(a.get('hands') or [])
        for i in range(min(len(cmds), len(pos))):
            c = cmds[i]
            if t <= end - 1 and isinstance(c, list) and c and c[0] == 'COLLECT_FERTILIZER':
                x, y = pos[i]
                tile = tiles[y][x] if 0 <= y < B and 0 <= x < len(tiles[y]) else None
                if isinstance(tile, dict) and 'animal' in tile and tile.get('fertilizer_available') and (x, y) not in collected:
                    later_collects += 1
            apply(i, c, False)
    cargo_end = sum(sum(d.values()) for d in inv)
    unsellable = sum(n for k, n in sh.items() if k in _FC_ANIMALS)
    destroyed = cargo_end + unsellable + _FC2_PAD - cap
    prices = observation['market']['prices']
    # drop order: units in order, items in insertion order; the last `destroyed` entries are destroyed and the j-th
    # skipped collect saves the j-th of them (saved[j])
    seq = [k for d in inv for k, n in d.items() for _ in range(max(0, _fc_int(n)))]
    saved = [float(_fc_int(prices.get(k, 0))) if k != 'FERTILIZER' else 0.0 for k in (seq[-destroyed:] if destroyed > 0 else [])]
    tail_items = set(seq[-destroyed:]) if destroyed > 0 else set()
    return destroyed, later_collects, saved, tail_items, cargo_end


def fc_agent(observation, configuration=None):
    action = _FC_PARENT[0](observation, configuration)
    try:
        step = int(observation['step']); day = step // 24; hour = step % 24
        if step == 0:
            _FC_REPORT.update(fires=0, skips=0, skips_a=0, skips_b=0, blocks={}, errors=0, fire_log=[])
        if not _FC_ON or not isinstance(action, dict) or hour < min(_FC_H0, _FC2_H0) or hour > 22 or day > 28:
            return action
        cap = 100
        if isinstance(configuration, dict):
            cap = _fc_int(configuration.get('shedCapacity', 100), 100)
        p = int(observation['player'])
        farm = observation['farms'][p]; priv = observation.get('private') or {}
        tiles = farm['tiles']
        invs = [dict(i) for i in (priv.get('inventories') or [])]
        shed = priv.get('shed') or {}
        positions = [farm['farmer']] + list(farm.get('hands') or [])
        units = [list(u) if isinstance(u, (list, tuple)) else ['PASS'] for u in
                 [action.get('farmer') or ['PASS']] + list(action.get('hands') or [])]
        n = min(len(units), len(positions))
        shed_total = sum(max(0, _fc_int(v)) for v in shed.values())
        carried = sum(max(0, _fc_int(v)) for inv in invs for v in inv.values())
        prod = 0; cons = 0; cands = []
        seen = set()
        for i in range(n):
            c = units[i]
            if not c:
                continue
            x, y = _fc_int(positions[i][0]), _fc_int(positions[i][1])
            tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else None
            inv = invs[i] if i < len(invs) else {}
            op = c[0]
            if op == 'HARVEST' and isinstance(tile, dict):
                prod += max(0, _fc_int(tile.get('yield_units', 0)))
            elif op == 'COLLECT_FERTILIZER' and isinstance(tile, dict) and 'animal' in tile \
                    and tile.get('fertilizer_available') and (x, y) not in seen:
                seen.add((x, y)); prod += 1; cands.append(i)
            elif op == 'FEED' and isinstance(tile, dict) and 'animal' in tile and not tile.get('fed_today') \
                    and _fc_int(inv.get('WHEAT', 0)) > 0:
                cons += 1
            elif op == 'FERTILIZE' and isinstance(tile, dict) and tile.get('kind') == 'PLANT' \
                    and _fc_int(inv.get('FERTILIZER', 0)) > 0:
                cons += 1
        if not cands:
            return action
        prices = observation['market']['prices']
        fert_q = float(_fc_int(prices.get('FERTILIZER', 0)))
        # rule A (v1)
        k1 = 0; tail1 = None; items1 = set(); T = shed_total + carried + prod - cons
        if hour >= _FC_H0:
            excess = T + _FC_TAIL - cap
            if excess > 0:
                if shed_total > _FC_SHED_MAX:
                    _fc_block('a_shed_sellable')
                else:
                    tail1, items1 = _fc_tail_price(invs, prices)
                    if tail1 is None:
                        _fc_block('a_tail_fert_only')
                    elif fert_q + _FC_MARGIN >= tail1:
                        _fc_block('a_fert_worth_more')
                    else:
                        k1 = min(excess, len(cands))
        # rule B (tape lookahead)
        k2 = 0; tail2 = None; items2 = set(); destroyed = 0; later = 0; cargo_end = 0
        saved = []
        if hour >= _FC2_H0 and '_rm_tape' in globals():
            # alignment check: the tape's commands for this step must match the parent's for (almost) every tape unit
            ta = _rm_tape(p, step)
            tc = [ta.get('farmer') or ['PASS']] + list(ta.get('hands') or []) if isinstance(ta, dict) else []
            mism = sum(1 for i in range(min(len(tc), n)) if list(tc[i] or ['PASS']) != list(units[i] or ['PASS']))
            if not tc or mism > _FC2_MAX_MISMATCH:
                _fc_block('b_misaligned')
                destroyed = 0
            elif T > cap + _FC2_TNOW_SLACK:
                _fc_block('b_tnow_over')
                destroyed = 0
            else:
                destroyed, later, saved, items2, cargo_end = _fc_project(observation, p, step, tiles, positions, units, invs, shed, cap)
                if destroyed > _FC2_MAXD:
                    _fc_block('b_destroyed_big')
                    destroyed = 0
            if destroyed > 0:
                want = destroyed - later
                if want <= 0:
                    _fc_block('b_later_collects')
                else:
                    # expected value of a saved unit = mean quote over the projected destroyed window
                    vals = [v if v > 0 else fert_q for v in saved]
                    mean_v = sum(vals) / len(vals) if vals else 0.0
                    if mean_v <= fert_q + _FC_MARGIN:
                        _fc_block('b_fert_worth_more')
                    else:
                        k2 = min(want, len(cands)); tail2 = mean_v
        if k1 <= 0 and k2 <= 0:
            return action
        rule = 'A' if k1 >= k2 else 'B'
        k = max(k1, k2)
        tail_p = tail1 if rule == 'A' else tail2
        items = items1 if rule == 'A' else items2
        fert_carried = sum(max(0, _fc_int(inv.get('FERTILIZER', 0))) for inv in invs) + max(0, _fc_int(shed.get('FERTILIZER', 0)))
        need = 0
        if '_rm_need' in globals():
            try:
                need = _fc_int((_rm_need(p, step) or {}).get('FERTILIZER', 0))
            except Exception:
                need = 0
        skipped = 0
        for i in reversed(cands):
            if skipped >= k:
                break
            if fert_carried - skipped - 1 < need:
                _fc_block('need_fert')
                break
            units[i] = ['PASS']
            skipped += 1
        if not skipped:
            return action
        out = dict(action)
        out['farmer'] = units[0]; out['hands'] = units[1:]
        _FC_REPORT['fires'] += 1; _FC_REPORT['skips'] += skipped
        _FC_REPORT['skips_a' if rule == 'A' else 'skips_b'] += skipped
        _FC_REPORT['fire_log'].append((step, rule, T, cargo_end, destroyed, later, skipped, fert_q, tail_p, sorted(items)))
        return out
    except Exception:
        _FC_REPORT['errors'] += 1
        return action


fc_agent.telemetry = _FC_REPORT
