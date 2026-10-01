


# ---------------------------------------------------------------------------
# W5 "presell" layer: twin-game one-step pre-sale of the parent's NEXT-step SELL lots.
#
# Mechanism (measured on 137 traced live twin games, w5presell/presell_measure.py h1_mod4: margin +65/game,
# 2se 48, own +37, est. flips LW5/WL1, total units per item exactly conserved = pure timing):
#   In twin games both farms replay the same route tape and the chassis' sell_lead makes both lead-sell the
#   same lots at the same step in per-unit lockstep at the same market-list index.  Selling the lot ONE step
#   before the twin gets the whole lot at the undepressed price and the twin then sells into our depression.
#   Rule at step t (day >= 6, hour <= 22, t % 4 != 0 so no town consumption happens between t and t+1, twin
#   game = _NT_D1[p] is not True): predict what the parent will SELL at t+1 for
#   X in {STRAWBERRY, MILK, WOOL, EGG, CARROT, TOMATO, MELON}:
#       plan = tape[t+1] SELLs - chassis suppression due at t+1 (lots it lead-sold this step, read from
#              _IMPL.chassis.players[p]['sell_state']) + the chassis' own lead-sale at t+1 of tape[t+2] lots
#              (when (t+1) % 4 != 0, t+2 not an unlock boundary, item has no SELL in tape[t+1]);
#   avail = shed[X] now - units this step's market list already sells; append SELL X min(plan, avail) after
#   the existing orders (never reorders, never exceeds 10 orders, never touches WHEAT/FERTILIZER, never an
#   item the tape PICKUPs next step).  The pre-sold quantity is then SUPPRESSED from the parent's next SELL
#   orders of that item (carried forward up to _W5PS_SUP_TTL steps, zero-qty orders kept so index slots stay),
#   so the lot only moves one step earlier and stock the parent meant to keep is never dumped (v1 smoke: 3
#   spare strawberries sold at $1 instead of $28 later).  Per-(item, tape-lot-step) bookkeeping prevents
#   pre-selling the same lot twice.
#   No unit commands are touched; any exception -> parent action unchanged; per-player state reset at step 0.
# ---------------------------------------------------------------------------
_W5PS_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_W5PS_ITEMS = ('STRAWBERRY', 'MILK', 'WOOL', 'EGG', 'CARROT', 'TOMATO', 'MELON')
_W5PS_TWIN_ONLY = True
_W5PS_MAX_ORDERS = 10
_W5PS_SUP_TTL = 8
_W5PS_STATE = {}


def _w5ps_new_report():
    return {'steps': 0, 'fires': 0, 'orders': 0, 'units': 0, 'errors': 0, 'units_by_item': {}, 'orders_by_item': {},
            'skip_day': 0, 'skip_hour': 0, 'skip_mod4': 0, 'skip_nt': 0, 'skip_noroute': 0, 'skip_noplan': 0,
            'skip_dup': 0, 'skip_pickup': 0, 'skip_noavail': 0, 'skip_full': 0, 'sup_units': 0, 'sup_orders': 0, 'sup_expired': 0}


_W5PS_REPORT = _w5ps_new_report()


def _w5ps_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    g = getattr(obj, 'get', None)
    if callable(g):
        try:
            return g(key, default)
        except Exception:
            return default
    return getattr(obj, key, default)


def _w5ps_sells(a):
    """[(item, qty)] of the SELL orders of a tape action dict (qty may be 0)."""
    out = []
    if not isinstance(a, dict):
        return out
    for o in a.get('market') or []:
        if isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] == 'SELL':
            try:
                q = int(o[2])
            except Exception:
                continue
            out.append((o[1], q))
    return out


def _w5ps_pickups(a):
    out = set()
    if not isinstance(a, dict):
        return out
    for u in [a.get('farmer')] + list(a.get('hands') or []):
        if isinstance(u, (list, tuple)) and len(u) >= 2 and u[0] == 'PICKUP':
            out.add(u[1])
    return out


def _w5ps_tape_action(routes, route, tt):
    r = 2 if tt >= 648 else route
    tape = routes.get(r)
    if tape is None or not (0 <= tt < len(tape)):
        return None
    return tape[tt]


def _w5ps_plan(chassis, route, step, sell_state):
    """{item: qty, lot_step} the parent is predicted to SELL at step+1 (presell items only).
    Returns {item: (qty, lot_step)} where lot_step is the tape step the lot belongs to."""
    nxt = step + 1
    a1 = _w5ps_tape_action(chassis.routes, route, nxt)
    plan = {}
    items1 = set()
    for item, q in _w5ps_sells(a1):
        items1.add(item)
        if item in _W5PS_ITEMS and q > 0:
            plan[item] = plan.get(item, 0) + q
    sup = {}
    if isinstance(sell_state, dict) and sell_state.get('due_step') == nxt:
        sup = dict(sell_state.get('suppress') or {})
    out = {}
    for item, q in plan.items():
        try:
            q = q - int(sup.get(item, 0) or 0)
        except Exception:
            pass
        if q > 0:
            out[item] = (q, nxt)
    if nxt % 4 != 0 and (step + 2) % 72 != 0 and step + 2 <= 718:
        a2 = _w5ps_tape_action(chassis.routes, route, step + 2)
        lead = {}
        for item, q in _w5ps_sells(a2):
            if item in _W5PS_ITEMS and q > 0 and item not in items1:
                lead[item] = lead.get(item, 0) + q
        for item, q in lead.items():
            if item not in out:
                out[item] = (q, step + 2)
    return out


def w5ps_agent(observation, configuration=None):
    action = _W5PS_PARENT[0](observation, configuration)
    try:
        step = int(_w5ps_get(observation, 'step', 0))
        p = int(_w5ps_get(observation, 'player', 0))
        st = _W5PS_STATE.get(p)
        if st is None or step == 0 or step < st['step']:
            st = _W5PS_STATE[p] = {'step': -1, 'presold': {}, 'sup': {}}
            if step == 0:
                _W5PS_REPORT.update(_w5ps_new_report())
        st['step'] = step
        R = _W5PS_REPORT
        R['steps'] += 1
        if st['sup'] and isinstance(action, dict):
            market = action.get('market')
            if isinstance(market, list):
                action = dict(action)
                market = [list(o) if isinstance(o, (list, tuple)) else o for o in market]
                action['market'] = market
                for i, o in enumerate(market):
                    if isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] == 'SELL' and o[1] in st['sup']:
                        item = o[1]
                        rem = st['sup'][item][0]
                        try:
                            q = max(0, int(o[2]))
                        except Exception:
                            continue
                        cut = min(q, rem)
                        if cut > 0:
                            market[i] = ['SELL', item, q - cut]
                            R['sup_units'] += cut
                            R['sup_orders'] += 1
                            rem -= cut
                        if rem <= 0:
                            del st['sup'][item]
                        else:
                            st['sup'][item] = (rem, st['sup'][item][1])
            for item in list(st['sup']):
                if step > st['sup'][item][1]:
                    R['sup_expired'] += st['sup'][item][0]
                    del st['sup'][item]
        day, hour = step // 24, step % 24
        if day < 6:
            R['skip_day'] += 1
            return action
        if hour > 22 or step + 1 > 718:
            R['skip_hour'] += 1
            return action
        if step % 4 == 0:
            R['skip_mod4'] += 1
            return action
        if _W5PS_TWIN_ONLY and (globals().get('_NT_D1') or {}).get(p) is True:
            R['skip_nt'] += 1
            return action
        if not isinstance(action, dict):
            return action
        chassis = _IMPL.chassis
        native = chassis.players.get(p) or {}
        route = native.get('route')
        if route not in chassis.routes:
            R['skip_noroute'] += 1
            return action
        plan = _w5ps_plan(chassis, route, step, native.get('sell_state'))
        if not plan:
            R['skip_noplan'] += 1
            return action
        market = action.get('market')
        action = dict(action)
        market = [list(o) if isinstance(o, (list, tuple)) else o for o in market] if isinstance(market, list) else []
        action['market'] = market
        already = {}
        for o in market:
            if isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] == 'SELL':
                try:
                    already[o[1]] = already.get(o[1], 0) + max(0, int(o[2]))
                except Exception:
                    pass
        private = _w5ps_get(observation, 'private') or {}
        shed = _w5ps_get(private, 'shed') or {}
        pick = _w5ps_pickups(_w5ps_tape_action(chassis.routes, route, step + 1))
        fired = False
        for item in _W5PS_ITEMS:
            if item not in plan:
                continue
            q, lot_step = plan[item]
            key = (item, lot_step)
            q -= st['presold'].get(key, 0)
            if q <= 0:
                R['skip_dup'] += 1
                continue
            if item in pick:
                R['skip_pickup'] += 1
                continue
            try:
                have = int(_w5ps_get(shed, item, 0) or 0)
            except Exception:
                have = 0
            avail = have - already.get(item, 0)
            if avail <= 0:
                R['skip_noavail'] += 1
                continue
            if len(market) >= _W5PS_MAX_ORDERS:
                R['skip_full'] += 1
                break
            qq = int(min(q, avail))
            market.append(['SELL', item, qq])
            already[item] = already.get(item, 0) + qq
            st['presold'][key] = st['presold'].get(key, 0) + qq
            old = st['sup'].get(item, (0, 0))
            st['sup'][item] = (old[0] + qq, step + _W5PS_SUP_TTL)
            R['orders'] += 1
            R['units'] += qq
            R['units_by_item'][item] = R['units_by_item'].get(item, 0) + qq
            R['orders_by_item'][item] = R['orders_by_item'].get(item, 0) + 1
            fired = True
        if fired:
            R['fires'] += 1
        if len(st['presold']) > 64:
            st['presold'] = {k: v for k, v in st['presold'].items() if k[1] >= step}
    except Exception:
        _W5PS_REPORT['errors'] += 1
    return action


w5ps_agent.telemetry = _W5PS_REPORT
