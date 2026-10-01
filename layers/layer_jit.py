


# ---------------------------------------------------------------------------
# 2026-09-30 eeshsaxena, own implementation. JIT (_JIT_): just-in-time premium sales against leader-template rivals,
# outermost layer on FO_B (research lens spec; market-only replay: +$1,099/game margin vs leader-template rivals, rival
# +$90; gated live games +$494, 4 L->W / 2 W->L of 136; UNGATED it is strongly negative, so the gate is mandatory).
# v2 (review fix round, 2026-09-30; v1 = md5 44b75812, stack FOB_JIT0.py): position-aware worst-case room lookahead,
#   atomic commit, sticky rival trigger, market params in the price curve, V9 'left' untouched, NTF yield, money hiding
#   + cash guard, non-wheat gate, fallback clamp + leak booking + hour-23 unhide (details in the sections below).
# ENGINE (kaggle_environments/envs/kaggriculture/kaggriculture.py): the interpreter (941-946) runs the unit actions,
#   then _process_market (544-628), then _town_consume(step) (728-749), then the day end (860-891: overnight inventory
#   drop, shop unlock). obs['step'] is the interpreter's step (core.py 626). SELL is per-unit lockstep (583-626): every
#   unit is quoted at the CURRENT market inventory with market.get('params') (597); a unit sold above $1 adds 1 to supply,
#   a $1 unit adds nothing (_commit_unit 653-661). Town drain of X at step k, after that step's market: k % 4 == 0 and an
#   unlocked shop instance lists X (single-item shops YARN_STORE / PET_CAFE take 2, 736-743), plus 1 of every
#   non-fertilizer product when k % 24 == 0 (745-747). The spec's drain rule is correct as written (intervals read from
#   the configuration when it carries townShopSellInterval / townCenterSellInterval). Shops unlock only at a day end
#   (884-891), so the list is fixed inside a day. A unit sold AFTER a drain meets a lower inventory (higher quote); a unit
#   sold after the rival's lot meets a higher one. JIT therefore sells after the drains and before the rival's habitual
#   hours. Within one market slot HIRE / BUY_LAND run before that slot's per-unit SELL / BUY loop, so revenue of slot i
#   funds only orders in slots > i.
# GATE (decided once, step 1, before the parent call): rival money <= our money - _JIT_GATE_MARGIN (250) AND the rival's
#   estimated NON-WHEAT step-0 spend >= _JIT_GATE_NONWHEAT (250; the research gate is "the rival's step-0 list holds a
#   BUY_ANIMAL", cheapest animal $300). Rival spend = its step-0 money - its step-1 money; its net step-0 wheat =
#   WHEAT inventory(0) - inventory(1) - step-0 town draw - our net wheat (our shed WHEAT(1) - shed(0); the shed is empty
#   before the step-0 market, so nothing is picked up), priced on the curve from inventory(0) and apportioned by units
#   with ours (lockstep interleave). Audit on 2,328 live replays vs the research gate (rival BUY_ANIMAL at 0): the money
#   test alone 455 TP / 25 FP / 0 FN; with the non-wheat test 455 / 8 / 0 (drops the 3 wheat-only public forks, the
#   SRI shiva twin and 13 wheat-only openers of the research's negative "no animal" population; the 8 left are seed-heavy
#   openers). Wheat-spend estimate |err| mean $1.85, max $35. Plus _NT_D1[p] is True at call time (latched at step 47,
#   FAMTW may reclassify; None / False = off). Gate off (or step 1 not seen) -> the parent's action object is returned
#   untouched and nothing is recorded. If step 0 was not seen: start money = configuration startingMoney (3000),
#   WHEAT inventory(0) = I0, our shed(0) = 0.
# RIVAL SALE LOG (self clock, the layer_h0s method): after our FINAL action at step s (s >= _JIT_REC_FROM = 167) we record,
#   for STRAWBERRY / MILK / WOOL / CARROT / TOMATO, the market inventory, the shops and OUR executed units
#   own = min(SELL qty of the item in market[:MAX_ORDERS], projected_shed(final action)[item]); projected_shed is the
#   chassis replica of the engine's PICKUP / DROP / PLACE (343-399), exact for these products, and no BUY can add them.
#   At s+1: moved = inv(s+1) - inv(s) + draw(s) = units sold above $1 by both players. If price(inv(s) + moved) > 1 (with
#   the game's market params) the floor was never reached and rival = moved - own is EXACT; otherwise only the lower
#   bound moved - min(own, moved) is known (rec_masked). A step is logged when rival >= _JIT_MIN_RIV (1). Error check: for
#   s % 24 != 23 the next shed must equal projected(s) - own(s) (own_mismatch counts the misses; 0 expected); rec_neg
#   counts negative recoveries.
# RULE (240 <= t <= 690, day d). For each item X that the parent's final list sells at t (executed units e > 0):
#   U = min(t + 12, next planned SELL-X step on the route tape (native / route 2 from 648, tape lot net of the r36 debts
#   booked so far), 24d + 22, 690). Hour h is blocked when the rival sold X at 24d' + h for some d' in {d-3, d-2, d-1}.
#   u_max = the step before the first blocked step in (t, U] (U when none). Hold only when u_max > t and a drain of X
#   happens in [t, u_max). Target u = u_max (_JIT_TARGET 'max', the spec) or the step after the last such drain
#   ('drain', arm: under the engine's market model it keeps the same drains with less exposure). Hold = every SELL X order
#   in the executed window becomes [] (slots kept); the e executed units become a pool (q, due u, start t).
#   RELEASE = re-issue ['SELL', X, q] at slot 0 after the leading HIREs: the first SELL X of the window grows and moves
#   there ('grow'), else insert when the list has < 10 orders, else take a [] / None / zero-qty slot, else merge two
#   same-item SELL lots separated only by HIRE / [] / zero orders ('merge2'), else retry next step ('full'). Triggers: due;
#   'rival' from v + 1 on when a rival X sale was detected at some v with start < v (sticky: a 'full' / guard miss at v + 1
#   retries every later step); hour >= 22 or step >= 690 ('deadline'); the parent itself sells X again ('next_sell', the
#   next planned SELL-X step; _JIT_NEXT 'split' = spec: that new lot is judged by the rule on its own; 'flush' arm: sold
#   with the pool; 'chain' arm: pool + lot re-judged together); gate off; room risk; cash risk.
# NTF YIELD (_JIT_NTF_YIELD): layer_ntfloor (inner) defers STRAWBERRY / WOOL crash-price lots in exactly the games JIT
#   gates on (_NT_D1 True, 576 <= t < _NTF_END / _NTF_END_ITEM), releases at a $60 first-unit quote or its deadline (hour
#   22; day 27 hour 20 so the wool is gone before layer_w6's 669 gate). JIT's pools are hidden from it, so the two layers
#   would hold the same units under different rules (and JIT would re-hold NTF's day-27 hour-20 release to 670).
#   'skip' (default, the review's minimal fix): no JIT hold of X while NTF is active for X (pools never cross a day and the
#   NTF window starts at hour 0, so no JIT pool of X exists there). 'cap' (arm): U is capped at NTF's deadline step and a
#   'due' / 'rival' release of X waits while the current quote is below _NTF_FLOOR, until that deadline. None: no yield.
# POOL HIDING (implementation choice): while a pool is held the parent is called with an observation whose private.shed
#   lacks the pool units (layer_mc / layer_wr pattern) and whose farms[p].money includes the pool's revenue projected at
#   hold time (est * q / q0; _JIT_HIDE_MONEY). The inner stack then plays the no-hold world the replay measured: r36
#   reservations, the herd-surplus seller, V92 dumps and phantom tape lots (clamp_sells False) cannot re-offer or eat the
#   pool, no second debt is booked for it, and every cash-gated inner decision (MC courier hire, V219 / CXTB, V233 / LV /
#   VE budgets, TV / T3 / SF / WR / BF / CC floors) sees the money it would have had. Phantom SELL X quantity of a held
#   item is blanked; units that still leave through the list (exception path) are counted as leak_units, booked in the
#   own-sales ledgers and taken off the pool. A pool left at a day change or at hour 23 is abandoned before the parent
#   call (units stay in the shed and are visible again, so ROOM23 / the chassis hour-23 room_guard plan the day-end drop
#   on the real shed).
# ROOM GUARD (the hidden pool still fills the real shed; DROP overflow is destroyed, 343-356; buys fail on a full shed,
#   667-668 / 682-683): with this step's final list, pre = shed total - pickups + DROP / PLACE inflow of shed-adjacent
#   units (uncapped) > 100 -> 'now'; post = pre - executed sells; risk when this step's buys push post past _JIT_ROOM (99,
#   'buy0'); when post + buys + the cargo every unit could DROP at t+1 exceeds it ('drop1': a unit can DROP at t+1 only
#   from a shed-access tile, i.e. where this step's move leaves it; its cargo then = carried + this step's harvest /
#   collect + PICKUP - DROP / PLACE; at hour 23 every unit, the day-end drop). This covers DROPs that are not on the
#   route tape (V219 workers, chassis pending commands, courier PLACEs, venture deliveries); or when the tape's cumulative
#   net buys up to the latest due would ('buy'; layer_ntfloor's guard). Risk -> no new hold this step and every pool is
#   released now.
# CASH GUARD (_JIT_CASH_GUARD): the final list is simulated in slot order with the REAL money (SELL revenue on the curve,
#   stock-capped; HIRE fib cost, BUY_LAND ladder, BUY_PRODUCT at inventory - 1, seed / animal list prices). If some buy /
#   hire unit is unaffordable while the parent's own list was affordable in its (hidden-money) view, JIT caused the
#   shortfall: no new hold and every pool is released at slot 0 (its revenue arrives before the later-slot buys).
# LEDGERS: our executed units per item differ from the parent's by delta = exec(final list, real projected shed) -
#   exec(parent list, parent's shed view); delta is booked signed in the rival-sale detectors' own-sales ledgers
#   (V9 race 'own' -> V92 P / Q, ORDERPRI2 own, race-clone prev_action, ER prev_sold, V2X wool) and in H0S's self-clock
#   record, so no inner detector reads our held / re-issued units as a rival sale. The V9 race 'left' (stock left to
#   race with) is NOT patched: it is the parent's hidden (no-hold) view, which is the world the replay measured.
# ATOMIC COMMIT: pool changes are built on a copy and swapped in at the end; a failure leaves the state untouched and the
#   step falls back to the parent's action. FALLBACK (guard miss / exception while pools are hidden): the parent's SELL
#   orders of each hidden item are clamped in slot order to the stock of the parent's own view, so phantom lots cannot
#   sell pool units; the pools stay held and their triggers retry next step.
# Never touches unit commands; never removes a HIRE / BUY / other item's order from the executed window (per-item SELL
#   totals of untouched items are kept); HIREs keep count and stay first when they were first; the list never grows past
#   max(len(parent list), MAX_ORDERS). Units only move in time (the pool stays in our shed; the engine caps every SELL at
#   the stock), so nothing is created or dropped. Any exception -> the parent's action (clamped as above).
# Knobs: _JIT_ON, _JIT_ITEMS, _JIT_FIRST, _JIT_LAST, _JIT_HORIZON, _JIT_DEADLINE_H, _JIT_GATE_MARGIN, _JIT_GATE_NONWHEAT,
#   _JIT_LOOKBACK_DAYS, _JIT_MIN_RIV, _JIT_TARGET, _JIT_NEXT, _JIT_ROOM, _JIT_NTF_YIELD, _JIT_HIDE_MONEY, _JIT_CASH_GUARD.
# Telemetry: _JIT_REPORT (gate / gate_diff / gate_nw / gate_rw / nt per player, holds, held units per item, releases by
#   reason, placements, blocked_cut (holds shortened by a blocked hour) + skip_blocked (holds prevented), skip_ntf /
#   ntf_wait, room / cash skips, recovery stats, own-sales check, leaks (+ booked), fallbacks, commit failures, h23
#   abandons, hidden money, projected revenue at hold vs release (est_*), errors), _JIT_LOG one row per event.
# ---------------------------------------------------------------------------
_JIT_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
import copy as _jit_cp
_JIT_ON = True
_JIT_ITEMS = ('STRAWBERRY', 'MILK', 'WOOL', 'CARROT', 'TOMATO')
_JIT_FIRST = 240
_JIT_LAST = 690
_JIT_HORIZON = 12
_JIT_DEADLINE_H = 22
_JIT_GATE_MARGIN = 250
_JIT_GATE_NONWHEAT = 250          # rival's estimated non-wheat step-0 spend (research gate: BUY_ANIMAL at 0; goose $300)
_JIT_LOOKBACK_DAYS = (1, 2, 3)
_JIT_MIN_RIV = 1
_JIT_TARGET = 'max'               # 'max' (spec: largest unblocked step) | 'drain' (arm: step after the last drain)
_JIT_NEXT = 'split'               # 'split' (spec) | 'flush' | 'chain'
_JIT_ROOM = 99
_JIT_SHED_CAP = 100
_JIT_NTF_YIELD = 'skip'           # 'skip' (review fix: no hold of an item while NTF is active for it) | 'cap' (arm) | None
_JIT_HIDE_MONEY = True            # the parent sees farms[p].money + the pools' projected revenue
_JIT_CASH_GUARD = True            # release every pool / hold nothing when the final list is unaffordable only because of JIT
_JIT_REC_FROM = 24 * (_JIT_FIRST // 24 - 3) - 1
_JIT_LOG_MAX = 5000
_JIT_SHOP_ITEMS = {
    'BAKERY': ('EGG', 'WHEAT'), 'PIZZA_SHOP': ('MILK', 'TOMATO', 'WHEAT'),
    'BRUNCH_SPOT': ('EGG', 'WHEAT', 'STRAWBERRY'), 'YARN_STORE': ('WOOL',),
    'ICE_CREAM_SHOP': ('STRAWBERRY', 'MILK', 'WHEAT'), 'PET_CAFE': ('CARROT',),
    'SMOOTHIE_SHOP': ('STRAWBERRY', 'MILK'),
    'FARMERS_MARKET': ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY'),
}
_JIT_SEED_COST = {'WHEAT': 10, 'CARROT': 20, 'TOMATO': 50, 'STRAWBERRY': 100, 'MELON': 80}
_JIT_ANIMAL_COST = {'GOOSE': 300, 'COW': 400, 'SHEEP': 500}
_JIT_LAND = (1000, 2000, 4000)
_JIT_MOVES = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}
_JIT_STATE = {}
_JIT_LOG = []


def _jit_new_report():
    return {'gate': {}, 'gate_diff': {}, 'gate_nw': {}, 'gate_rw': {}, 'nt': {}, 'active_steps': 0, 'pool_steps': 0,
            'max_pool': 0, 'holds': 0, 'held_units': 0, 'holds_item': {}, 'units_item': {}, 'hold_len_sum': 0,
            'reissues': 0, 'reissued_units': 0, 'rel_due': 0, 'rel_rival': 0, 'rel_deadline': 0,
            'rel_next_sell': 0, 'rel_room': 0, 'rel_cash': 0, 'rel_gate': 0, 'chain': 0,
            'place_grow': 0, 'place_insert': 0, 'place_slot': 0, 'place_merge2': 0, 'place_none': 0,
            'place_full': 0, 'left_units': 0, 'abandoned': 0, 'abandoned_units': 0, 'h23_abandon': 0,
            'skip_bound': 0, 'skip_blocked': 0, 'skip_nodrain': 0, 'skip_room': 0, 'skip_cash': 0, 'skip_guard': 0,
            'skip_ntf': 0, 'ntf_wait': 0,
            'blocked_cut': 0, 'room_why': {},
            'rec_steps': 0, 'rec_exact': 0, 'rec_masked': 0, 'rec_neg': 0, 'rec_neg_units': 0,
            'riv_logged': 0, 'riv_units': 0, 'riv_item': {},
            'own_checks': 0, 'own_mismatch': 0, 'own_mismatch_units': 0,
            'leak_units': 0, 'leak_booked': 0, 'pickup_leak': 0, 'overflow_seen': 0,
            'fallbacks': 0, 'fb_clamped': 0, 'commit_fail': 0,
            'money_steps': 0, 'money_max': 0,
            'est_hold': 0, 'est_release': 0, 'est_gain': 0,
            'ledger_fixes': 0, 'errors': 0, 'telemetry_errors': 0}


_JIT_REPORT = _jit_new_report()


def _jit_reset_report():
    _JIT_REPORT.clear()
    _JIT_REPORT.update(_jit_new_report())
    del _JIT_LOG[:]


def _jit_log(row):
    if len(_JIT_LOG) < _JIT_LOG_MAX:
        _JIT_LOG.append(row)


def _jit_i(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _jit_new_state():
    return {'step': -1, 'gate': None, 'pool': {}, 'riv': {X: set() for X in _JIT_ITEMS}, 'rec': None,
            'si': 4, 'ci': 24, 'hidden': {}, 'hidden_money': 0.0, 'released_now': set(), 'held_now': set(),
            'sh_r': None, 'open': None}


def _jit_clone(o):
    try:
        return _jit_cp.copy(o)
    except Exception:
        return dict(o)


def _jit_set(o, k, v):
    dict.__setitem__(o, k, v)
    d = getattr(o, '__dict__', None)
    if isinstance(d, dict):
        d[k] = v


def _jit_is_sell(o, item=None):
    return isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] == 'SELL' and (item is None or o[1] == item)


def _jit_sells(market, item):
    return sum(max(0, _jit_i(o[2])) for o in list(market or [])[:MAX_ORDERS] if _jit_is_sell(o, item))


def _jit_exec(market, shed):
    """Executed SELL units per item in the executed window (per-item total capped by the projected shed; no BUY can add
    a JIT item, so the cap is the stock at market time)."""
    out = {}
    for o in list(market or [])[:MAX_ORDERS]:
        if _jit_is_sell(o):
            it = o[1]
            out[it] = min(out.get(it, 0) + max(0, _jit_i(o[2])), max(0, _jit_i((shed or {}).get(it, 0))))
    return out


def _jit_intervals(cfg):
    si, ci = 4, 24
    try:
        if cfg is not None:
            si = max(1, _jit_i(_get(cfg, 'townShopSellInterval', 4), 4))
            ci = max(1, _jit_i(_get(cfg, 'townCenterSellInterval', 24), 24))
    except Exception:
        si, ci = 4, 24
    return si, ci


def _jit_draw(shops, k, si, ci):
    """Units of each JIT item the town removes after step k's market (kaggriculture.py 736-747)."""
    draw = dict.fromkeys(_JIT_ITEMS, 0)
    if k % si == 0:
        for s in shops:
            its = _JIT_SHOP_ITEMS.get(s, ())
            for it in its:
                if it in draw:
                    draw[it] += 2 if len(its) == 1 else 1
    if k % ci == 0:
        for it in draw:
            draw[it] += 1
    return draw


def _jit_drains(X, k, shops, si, ci):
    if k % ci == 0:
        return True
    return k % si == 0 and any(X in _JIT_SHOP_ITEMS.get(s, ()) for s in shops)


def _jit_params(obs):
    try:
        return obs['market'].get('params')
    except Exception:
        return None


def _jit_price(X, inv, params=None):
    f = globals().get('_r37_market_price')
    return _jit_i(f(X, int(inv), params)) if callable(f) else None


def _jit_seq(X, inv, q, params=None):
    """Projected revenue of q units sold from inventory inv (engine curve with the game's params, $1 units add no
    supply)."""
    f = globals().get('_r37_market_price')
    if not callable(f):
        return 0
    tot = 0
    x = int(inv)
    for _ in range(max(0, min(int(q), 400))):
        pr = int(f(X, x, params))
        tot += pr
        if pr > 1:
            x += 1
    return tot


def _jit_tape(p, t):
    try:
        native = _IMPL.chassis.players.get(p) or {}
        tape = _IMPL.chassis.routes.get(2 if t >= 648 else native.get('route'))
        if not tape or t < 0 or t >= len(tape) or not isinstance(tape[t], dict):
            return {}
        return tape[t]
    except Exception:
        return {}


def _jit_debts(p):
    try:
        return _IMPL.chassis.players[p]['sell_state'].get('r36_debts') or {}
    except Exception:
        return {}


def _jit_tape_net(p, k, X, debts):
    q = _jit_sells(_jit_tape(p, k).get('market') or [], X)
    if q <= 0:
        return 0
    return max(0, q - _jit_i((debts.get(k) or {}).get(X, 0)))


def _jit_blocked(st, X, k):
    d, h = divmod(k, 24)
    riv = st['riv'][X]
    return any((24 * (d - b) + h) in riv for b in _JIT_LOOKBACK_DAYS if d - b >= 0)


# ---- NTF yield ------------------------------------------------------------------------------------------------------
def _jit_ntf_active(X, step, nt):
    """layer_ntfloor's own activity test for item X at step (its _ntf_core 'active')."""
    g = globals()
    if nt is not True or not g.get('_NTF_ON', False) or X not in (g.get('_NTF_ITEMS') or ()):
        return False
    end = _jit_i(g.get('_NTF_END', 696), 696)
    end_i = _jit_i((g.get('_NTF_END_ITEM') or {}).get(X, end), end)
    return _jit_i(g.get('_NTF_FIRST', 576), 576) <= step < min(end, end_i)


def _jit_ntf_dead(step):
    """NTF's release deadline step of step's day (hour 22; day 27: hour 20)."""
    g = globals()
    d = step // 24
    h = _jit_i(g.get('_NTF_D27_DEADLINE_H', 20), 20) if d == 27 else _jit_i(g.get('_NTF_DEADLINE_H', 22), 22)
    return 24 * d + h


def _jit_target(st, p, X, t, shops, debts, si, ci, cap=None):
    """(u, why, info): u > t = hold until u; why in ('ok', 'bound', 'blocked', 'nodrain')."""
    d = t // 24
    U = min(t + _JIT_HORIZON, 24 * d + _JIT_DEADLINE_H, _JIT_LAST)
    if cap is not None:
        U = min(U, cap)
    nxt = None
    for k in range(t + 1, U + 1):
        if _jit_tape_net(p, k, X, debts) > 0:
            nxt = k
            break
    if nxt is not None:
        U = min(U, nxt)
    info = {'U': U, 'nxt': nxt, 'b': None, 'umax': t, 'nd': 0}
    if U <= t:
        return t, 'bound', info
    b = next((k for k in range(t + 1, U + 1) if _jit_blocked(st, X, k)), None)
    umax = U if b is None else b - 1
    info['b'] = b
    info['umax'] = umax
    if umax <= t:
        return t, 'blocked', info
    drains = [k for k in range(t, umax) if _jit_drains(X, k, shops, si, ci)]
    info['nd'] = len(drains)
    if not drains:
        return t, 'nodrain', info
    u = min(umax, drains[-1] + 1) if _JIT_TARGET == 'drain' else umax
    return u, 'ok', info


# ---- market list placement ------------------------------------------------------------------------------------------
def _jit_lead(new):
    k = 0
    while k < len(new) and isinstance(new[k], (list, tuple)) and len(new[k]) >= 1 and new[k][0] == 'HIRE':
        k += 1
    return k


def _jit_free(o):
    if o is None:
        return True
    if not isinstance(o, (list, tuple)):
        return False
    if len(o) == 0:
        return True
    return len(o) >= 3 and o[0] in ('SELL', 'BUY_PRODUCT', 'BUY_SEED', 'BUY_ANIMAL') and _jit_i(o[2]) <= 0


def _jit_is_hire(o):
    return isinstance(o, (list, tuple)) and len(o) >= 1 and o[0] == 'HIRE'


def _jit_merge_pair(new, prices):
    """Merge one pair of non-zero SELL lots of one item separated only by HIRE / [] / None / zero orders (later slot into
    the earlier one, cheapest lot first). Returns the shorter list or None."""
    win = min(len(new), MAX_ORDERS)
    best = None
    for i in range(win):
        x = new[i]
        if not _jit_is_sell(x) or _jit_i(x[2]) <= 0:
            continue
        for j in range(i - 1, -1, -1):
            y = new[j]
            if _jit_is_sell(y, x[1]) and _jit_i(y[2]) > 0:
                v = _jit_i(prices.get(x[1], 0)) * _jit_i(x[2])
                if best is None or v < best[0]:
                    best = (v, j, i)
                break
            if not (_jit_free(y) or _jit_is_hire(y)):
                break
    if best is None:
        return None
    _, j, i = best
    out = list(new)
    out[j] = ['SELL', out[j][1], _jit_i(out[j][2]) + _jit_i(out[i][2])]
    del out[i]
    return out


def _jit_place(market, item, q, prices):
    """New list with ['SELL', item, q] at slot 0 after the leading HIREs. Returns (list, how) or (None, 'full')."""
    new = [list(o) if isinstance(o, (list, tuple)) else o for o in market]
    lead = _jit_lead(new)
    win = min(len(new), MAX_ORDERS)
    j = next((i for i in range(lead, win) if _jit_is_sell(new[i], item)), None)
    if j is not None:
        o = new.pop(j)
        new.insert(lead, ['SELL', item, max(0, _jit_i(o[2])) + q])
        return new, 'grow'
    if len(new) < MAX_ORDERS:
        new.insert(lead, ['SELL', item, q])
        return new, 'insert'
    k = next((i for i in range(lead, win) if _jit_free(new[i])), None)
    if k is not None:
        new.pop(k)
        new.insert(lead, ['SELL', item, q])
        return new, 'slot'
    m = _jit_merge_pair(new, prices)
    if m is not None and len(m) < len(new):
        m.insert(_jit_lead(m), ['SELL', item, q])
        return m, 'merge2'
    return None, 'full'


def _jit_guard(old, new, touched):
    """Window invariants: HIRE count kept and the leading HIRE run not shortened; the list never grows past
    max(len(old), MAX_ORDERS); every non-SELL order of the old window is still in the new window; per-item SELL totals of
    untouched items are kept (merge2 may fuse two of their lots)."""
    ow = list(old)[:MAX_ORDERS]
    nw = list(new)[:MAX_ORDERS]
    if len(new) > max(len(old), MAX_ORDERS):
        return False
    if sum(1 for o in ow if _jit_is_hire(o)) != sum(1 for o in nw if _jit_is_hire(o)):
        return False
    if _jit_lead(nw) < _jit_lead(ow):
        return False
    need = {}
    have = {}
    for o in ow:
        if _jit_free(o) or _jit_is_hire(o) or _jit_is_sell(o):
            continue
        k = repr(list(o) if isinstance(o, (list, tuple)) else o)
        need[k] = need.get(k, 0) + 1
    for o in nw:
        if _jit_free(o) or _jit_is_hire(o) or _jit_is_sell(o):
            continue
        k = repr(list(o) if isinstance(o, (list, tuple)) else o)
        have[k] = have.get(k, 0) + 1
    if need != have:
        return False
    items = {o[1] for o in ow + nw if _jit_is_sell(o)} - set(touched)
    for it in items:
        if _jit_sells(ow, it) != _jit_sells(nw, it):
            return False
    return True


# ---- room guard -----------------------------------------------------------------------------------------------------
def _jit_units(a):
    a = a if isinstance(a, dict) else {}
    return [a.get('farmer') or ['PASS']] + list(a.get('hands') or [])


def _jit_buys(market):
    return sum(max(0, _jit_i(o[2])) for o in list(market or [])[:MAX_ORDERS]
               if isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] in ('BUY_PRODUCT', 'BUY_ANIMAL'))


def _jit_carried(view, i):
    return sum(max(0, _jit_i(v)) for v in (view.inv(i) or {}).values())


def _jit_produced(units, view):
    out = []
    for i in range(len(view.positions)):
        a = units[i] if i < len(units) else None
        n = 0
        try:
            if isinstance(a, (list, tuple)) and a and a[0] in ('HARVEST', 'COLLECT_FERTILIZER'):
                pos = view.positions[i]
                tile = view.tiles[int(pos[1])][int(pos[0])]
                if isinstance(tile, dict):
                    if a[0] == 'HARVEST':
                        n = max(0, _jit_i(tile.get('yield_units', 0)))
                    elif tile.get('fertilizer_available'):
                        n = 1
        except Exception:
            n = 0
        out.append(n)
    return out


def _jit_flow(units, view, adj, extra=None):
    """(inflow, pickups) of unit commands; DROP = everything carried, PLACE of a product = min(qty, carried); uncapped.
    adj: only shed-adjacent units (this step); else every unit (the tape's next step: positions unknown)."""
    inflow = pick = 0
    for i in range(min(len(units), len(view.positions))):
        if adj and not _shed_adjacent(view.positions[i], view.board):
            continue
        a = units[i]
        if not isinstance(a, (list, tuple)) or not a:
            continue
        op = a[0]
        inv = view.inv(i) or {}
        carried = _jit_carried(view, i) + (extra[i] if extra and i < len(extra) else 0)
        if op == 'DROP':
            inflow += carried
        elif op == 'PLACE' and len(a) >= 2 and a[1] not in ANIMAL_STRUCTURE:
            qty = max(0, _jit_i(a[2]) if len(a) >= 3 else 1)
            inflow += min(qty, carried if extra else max(0, _jit_i(inv.get(a[1], 0))))
        elif op == 'PICKUP' and len(a) >= 2 and adj:
            qty = max(0, _jit_i(a[2]) if len(a) >= 3 else 1)
            pick += min(qty, max(0, _jit_i(view.shed.get(a[1], 0))))
    return inflow, pick


def _jit_moved(pos, a, board):
    """Unit position after this step's command (engine: a move stays inside the board, no collision)."""
    try:
        x, y = int(pos[0]), int(pos[1])
    except Exception:
        return pos
    if isinstance(a, (list, tuple)) and a and a[0] in _JIT_MOVES:
        dx, dy = _JIT_MOVES[a[0]]
        if 0 <= x + dx < board and 0 <= y + dy < board:
            return (x + dx, y + dy)
    return (x, y)


def _jit_cargo_next(units, view, prod):
    """(cargo that can reach the shed at t+1, cargo of every unit). A unit can DROP / PLACE at t+1 only from a
    shed-access tile, i.e. where this step's command leaves it; what it carries then = carried + this step's harvest /
    collect + PICKUP - DROP / PLACE (engine 343-411; pickup capped by the shed stock at the start of the step)."""
    near = allc = 0
    for i in range(len(view.positions)):
        a = units[i] if i < len(units) else None
        pos = view.positions[i]
        inv = view.inv(i) or {}
        after = _jit_carried(view, i) + (prod[i] if i < len(prod) else 0)
        op = a[0] if isinstance(a, (list, tuple)) and a else None
        adj = _shed_adjacent(pos, view.board)
        if adj and op == 'DROP':
            after = 0
        elif adj and op == 'PLACE' and len(a) >= 2 and a[1] not in ANIMAL_STRUCTURE:
            qty = _jit_i(a[2]) if len(a) >= 3 else 1
            after -= min(max(0, qty), max(0, _jit_i(inv.get(a[1], 0))))
        elif adj and op == 'PICKUP' and len(a) >= 2:
            qty = _jit_i(a[2]) if len(a) >= 3 else 1
            after += min(max(0, qty), max(0, _jit_i(view.shed.get(a[1], 0))))
        after = max(0, after)
        allc += after
        if _shed_adjacent(_jit_moved(pos, a, view.board), view.board):
            near += after
    return near, allc


def _jit_room_risk(obs, action, final_market, p, step, view_r, sh_r, maxdue):
    shed = obs['private'].get('shed') or {}
    tot0 = sum(max(0, _jit_i(v)) for v in shed.values())
    units = _jit_units(action)
    inflow0, pick0 = _jit_flow(units, view_r, True)
    pre = tot0 - pick0 + inflow0
    if pre > _JIT_SHED_CAP:
        return 'now'
    post = pre - sum(_jit_exec(final_market, sh_r).values())
    qb0 = _jit_buys(final_market)
    if qb0 > 0 and post + qb0 > _JIT_ROOM:
        return 'buy0'
    post += qb0
    near, allc = _jit_cargo_next(units, view_r, _jit_produced(units, view_r))
    inflow1 = allc if step % 24 == 23 else near
    if inflow1 > 0 and post + inflow1 > _JIT_ROOM:
        return 'drop1'
    cum = post + inflow1
    for t in range(step + 1, min(719, maxdue + 1)):
        tm = _jit_tape(p, t).get('market') or []
        qb = _jit_buys(tm)
        if qb > 0 and cum + qb > _JIT_ROOM:
            return 'buy'
        cum = max(0, cum + qb - sum(max(0, _jit_i(o[2])) for o in tm[:MAX_ORDERS] if _jit_is_sell(o)))
    return None


# ---- cash guard -----------------------------------------------------------------------------------------------------
def _jit_fib(n):
    a, b = 1, 1
    for _ in range(max(0, int(n))):
        a, b = b, a + b
    return a


def _jit_cash_ok(market, obs, p, stock, money, params):
    """True when every HIRE / BUY_LAND / BUY_* unit of the executed window is affordable in slot order (engine 566-628,
    653-700): SELL revenue projected on the curve from the current inventory and capped by the stock, BUY_PRODUCT quoted
    at inventory - 1, hires fib(hires_today), the land ladder, list seed / animal prices. The rival's lockstep units are
    ignored (the same in every list this is compared with)."""
    f = globals().get('_r37_market_price')
    if not callable(f):
        return True
    farm = obs['farms'][p]
    m = float(money)
    inv = {k: _jit_i(v) for k, v in dict(obs['market']['inventory']).items()}
    left = {k: max(0, _jit_i(v)) for k, v in dict(stock or {}).items()}
    h = _jit_i(farm.get('hires_today', 0))
    nq = len(list(farm.get('unlocked_quadrants') or [])) - 1
    for o in list(market or [])[:MAX_ORDERS]:
        if not isinstance(o, (list, tuple)) or not o:
            continue
        op = o[0]
        if op == 'HIRE':
            c = _jit_fib(h)
            if m < c:
                return False
            m -= c
            h += 1
            continue
        if op == 'BUY_LAND':
            if 0 <= nq < len(_JIT_LAND):
                if m < _JIT_LAND[nq]:
                    return False
                m -= _JIT_LAND[nq]
                nq += 1
            continue
        if len(o) < 3:
            continue
        q = _jit_i(o[2])
        X = o[1]
        if q <= 0:
            continue
        if op == 'SELL' and X in inv:
            n = min(q, left.get(X, 0))
            left[X] = left.get(X, 0) - n
            x = inv[X]
            for _ in range(min(n, 400)):
                pr = int(f(X, x, params))
                m += pr
                if pr > 1:
                    x += 1
            inv[X] = x
        elif op == 'BUY_PRODUCT' and X in ('WHEAT', 'FERTILIZER') and X in inv:
            x = inv[X]
            for _ in range(min(q, 400)):
                pr = int(f(X, x - 1, params))
                if m < pr:
                    return False
                m -= pr
                x -= 1
            inv[X] = x
            left[X] = left.get(X, 0) + q
        elif op == 'BUY_SEED' and X in _JIT_SEED_COST:
            if m < _JIT_SEED_COST[X] * q:
                return False
            m -= _JIT_SEED_COST[X] * q
        elif op == 'BUY_ANIMAL' and X in _JIT_ANIMAL_COST:
            if m < _JIT_ANIMAL_COST[X] * q:
                return False
            m -= _JIT_ANIMAL_COST[X] * q
    return True


# ---- ledgers --------------------------------------------------------------------------------------------------------
def _jit_patch_own(player, step, item, q, final_market):
    """Signed own-sales patch (q > 0 book, q < 0 un-book, clamped at 0) in the ledgers layer_h0f patches, plus H0S's
    self-clock record. The V9 race 'left' is not touched (the parent's hidden view is the no-hold world). Race clone
    keeps only item presence: an un-book drops the item's SELLs from prev_action when the final window no longer sells
    it; a book appends ['SELL', item, q]."""
    n = 0
    rep = _JIT_REPORT
    g = globals()
    try:
        race = (g.get('_V9_RACE') or {}).get(player)
        if race and race.get('prev') and race['prev'].get('step') == step:
            own = race['prev'].setdefault('own', {})
            own[item] = max(0, _jit_i(own.get(item, 0)) + q)
            n += 1
    except Exception:
        rep['errors'] += 1
    try:
        or2 = (g.get('_OR2_STATE') or {}).get(player)
        if or2 and or2.get('prev') and or2['prev'].get('step') == step:
            own = or2['prev'].setdefault('own', {})
            own[item] = max(0, _jit_i(own.get(item, 0)) + q)
            n += 1
    except Exception:
        rep['errors'] += 1
    try:
        rs = (g.get('_RACE_STATE') or {}).get(player)
        if rs and rs.get('prev') is not None and rs.get('prev_action') is not None and rs['prev'].get('step') == step:
            pa = rs['prev_action']
            if q > 0:
                rs['prev_action'] = dict(pa, market=list(pa.get('market') or []) + [['SELL', item, q]])
                n += 1
            elif q < 0 and _jit_sells(final_market or [], item) <= 0:
                rs['prev_action'] = dict(pa, market=[o for o in list(pa.get('market') or [])
                                                     if not (isinstance(o, (list, tuple)) and len(o) >= 2
                                                             and o[0] == 'SELL' and o[1] == item)])
                n += 1
    except Exception:
        rep['errors'] += 1
    try:
        est = (g.get('_ER_STATE') or {}).get(player)
        if est and est.get('prev_proj') is not None and est.get('prev_step') == step:
            ps = est.setdefault('prev_sold', {})
            ps[item] = max(0, _jit_i(ps.get(item, 0)) + q)
            n += 1
    except Exception:
        rep['errors'] += 1
    try:
        if item == 'WOOL':
            vx = (g.get('_VX_STATE') or {}).get(player)
            pv = vx.get('prev') if isinstance(vx, dict) else None
            if isinstance(pv, dict) and pv.get('step') == step:
                pv['own'] = max(0, _jit_i(pv.get('own', 0) or 0) + q)
                n += 1
    except Exception:
        rep['errors'] += 1
    try:
        if item == g.get('_H0S_ITEM'):
            hs = (g.get('_H0S_STATE') or {}).get(player)
            r = (hs.get('rec') or {}).get(step) if isinstance(hs, dict) else None
            if isinstance(r, dict) and 'own' in r:
                r['own'] = max(0, _jit_i(r['own']) + q)
                n += 1
    except Exception:
        rep['errors'] += 1
    return n


# ---- per-step pieces ------------------------------------------------------------------------------------------------
def _jit_open(obs, p, st):
    """Step 0 (before any order): both players' money, the WHEAT inventory, our shed WHEAT, the shops."""
    farms = obs['farms']
    st['open'] = dict(m_own=float(farms[p]['money']), m_riv=float(farms[1 - p]['money']),
                      winv=_jit_i(obs['market']['inventory'].get('WHEAT', 0)),
                      wshed=_jit_i((obs['private'].get('shed') or {}).get('WHEAT', 0)),
                      shops=list(obs['town']['unlocked_shops']))


def _jit_wheat_cost(n_me, n_other, inv0, params):
    """Projected spend of n_me net wheat units when n_me + n_other are bought at one step from inventory inv0 (buy quote
    at inventory - 1, units apportioned: the lockstep interleaves both players)."""
    tot = n_me + max(0, n_other)
    if n_me <= 0 or tot <= 0:
        return 0.0
    f = globals().get('_r37_market_price')
    if not callable(f):
        return 25.0 * n_me
    s = sum(int(f('WHEAT', int(inv0) - k - 1, params)) for k in range(min(tot, 3000)))
    return s * n_me / float(tot)


def _jit_gate(obs, p, st, cfg):
    rep = _JIT_REPORT
    farms = obs['farms']
    own = float(farms[p]['money'])
    riv = float(farms[1 - p]['money'])
    gap = own - riv
    o0 = st.get('open') or {}
    start = 3000.0
    try:
        if cfg is not None:
            start = float(_jit_i(_get(cfg, 'startingMoney', 3000), 3000))
    except Exception:
        start = 3000.0
    params = _jit_params(obs)
    try:
        I0 = _jit_i((params or _R37_MARKET_PARAMS)['WHEAT']['I0'], 10000)
    except Exception:
        I0 = 10000
    w0 = _jit_i(o0.get('winv', I0), I0)
    w1 = _jit_i(obs['market']['inventory'].get('WHEAT', w0), w0)
    shops0 = o0.get('shops')
    if shops0 is None:
        shops0 = list(obs['town']['unlocked_shops'])
    draw0 = 0
    if 0 % st['si'] == 0:
        for s in shops0:
            its = _JIT_SHOP_ITEMS.get(s, ())
            if 'WHEAT' in its:
                draw0 += 2 if len(its) == 1 else 1
    if 0 % st['ci'] == 0:
        draw0 += 1
    our_w = _jit_i((obs['private'].get('shed') or {}).get('WHEAT', 0)) - _jit_i(o0.get('wshed', 0))
    riv_w = max(0, w0 - w1 - draw0 - our_w)
    riv_nw = float(o0.get('m_riv', start)) - riv - _jit_wheat_cost(riv_w, our_w, w0, params)
    st['gate'] = bool(gap >= _JIT_GATE_MARGIN and riv_nw >= _JIT_GATE_NONWHEAT)
    rep['gate'][p] = st['gate']
    rep['gate_diff'][p] = round(gap, 3)
    rep['gate_nw'][p] = round(riv_nw, 1)
    rep['gate_rw'][p] = riv_w


def _jit_observe(obs, st, step):
    """Rival units of each JIT item sold at step - 1 (see header)."""
    rec = st.get('rec')
    st['rec'] = None
    if not rec or rec['step'] != step - 1:
        return
    rep = _JIT_REPORT
    t = step - 1
    inv = obs['market']['inventory']
    params = _jit_params(obs)
    shed = obs['private'].get('shed') or {}
    draw = _jit_draw(rec['shops'], t, rec['si'], rec['ci'])
    rep['rec_steps'] += 1
    for X in _JIT_ITEMS:
        moved = _jit_i(inv.get(X, 0)) - rec['inv'][X] + draw[X]
        own = rec['own'].get(X, 0)
        pr = _jit_price(X, rec['inv'][X] + moved, params)
        if pr is not None and pr <= 1:
            riv = moved - min(own, max(0, moved))
            rep['rec_masked'] += 1
        else:
            riv = moved - own
            rep['rec_exact'] += 1
        if riv < 0:
            rep['rec_neg'] += 1
            rep['rec_neg_units'] += -riv
        elif riv >= _JIT_MIN_RIV:
            st['riv'][X].add(t)
            rep['riv_logged'] += 1
            rep['riv_units'] += riv
            rep['riv_item'][X] = rep['riv_item'].get(X, 0) + 1
        if t % 24 != 23:
            rep['own_checks'] += 1
            exp = rec['proj'].get(X, 0) - own
            got = _jit_i(shed.get(X, 0))
            if got != exp:
                rep['own_mismatch'] += 1
                rep['own_mismatch_units'] += abs(got - exp)


def _jit_parent_obs(obs, st, p):
    hide = {X: pl['q'] for X, pl in st['pool'].items() if pl['q'] > 0}
    if not hide:
        return obs
    pr = obs['private']
    shed = dict(pr['shed'])
    for X, q in hide.items():
        shed[X] = max(0, _jit_i(shed.get(X, 0)) - q)
    pr2 = _jit_clone(pr)
    _jit_set(pr2, 'shed', shed)
    o = _jit_clone(obs)
    _jit_set(o, 'private', pr2)
    st['hidden'] = hide
    if _JIT_HIDE_MONEY:
        add = float(round(sum(pl['est'] * pl['q'] / float(max(1, pl['q0']))
                              for pl in st['pool'].values() if pl['q'] > 0)))
        if add > 0:
            farms = list(obs['farms'])
            f2 = _jit_clone(farms[p])
            _jit_set(f2, 'money', float(farms[p]['money']) + add)
            farms[p] = f2
            _jit_set(o, 'farms', farms)
            st['hidden_money'] = add
            _JIT_REPORT['money_steps'] += 1
            _JIT_REPORT['money_max'] = max(_JIT_REPORT['money_max'], int(add))
    return o


def _jit_build(market, rel, P, blank, prices):
    """Final list: SELL orders of the blanked items become [] in the window, then each released pool is placed at slot 0
    (lowest value first, so the most valuable lot ends first). Returns (list, {item: how})."""
    new = [list(o) if isinstance(o, (list, tuple)) else o for o in market]
    for i in range(min(len(new), MAX_ORDERS)):
        if _jit_is_sell(new[i]) and new[i][1] in blank:
            new[i] = []
    placed = {}
    for X in sorted(rel, key=lambda it: (_jit_i(prices.get(it, 0)) * P.get(it, 0), it)):
        q = P.get(X, 0)
        if q <= 0:
            placed[X] = 'none'
            continue
        m, how = _jit_place(new, X, q, prices)
        if m is None:
            placed[X] = 'full'
            continue
        new = m
        placed[X] = how
    return new, placed


def _jit_core(obs, pobs, action, st, step, p):
    """Plan this step. Returns (action to send, commit dict or None). Mutates nothing but st['sh_r']."""
    rep = _JIT_REPORT
    nt = (globals().get('_NT_D1') or {}).get(p)
    rep['nt'][p] = nt
    enabled = bool(_JIT_ON and st['gate'] is True and nt is True)
    pools = st['pool']
    window = _JIT_FIRST <= step <= _JIT_LAST
    if not pools and not (enabled and window):
        return action, None
    market = list(action.get('market') or [])
    view_p = FarmView(pobs)
    sh_p = projected_shed(action, view_p)
    if pobs is obs:
        view_r, sh_r = view_p, sh_p
    else:
        view_r = FarmView(obs)
        sh_r = projected_shed(action, view_r)
    st['sh_r'] = sh_r
    ex_p = _jit_exec(market, sh_p)
    if not pools and not any(ex_p.get(X, 0) > 0 for X in _JIT_ITEMS):
        return action, None
    rep['active_steps'] += 1
    d, hour = divmod(step, 24)
    prices = obs['market']['prices']
    inv = obs['market']['inventory']
    params = _jit_params(obs)
    shops = list(obs['town']['unlocked_shops'])
    si, ci = st['si'], st['ci']
    debts = _jit_debts(p)
    g = globals()
    # pool units still in the real shed after this step's unit actions (a PICKUP / capped DROP can take some)
    P = {X: min(pl['q'], max(0, _jit_i(sh_r.get(X, 0)) - _jit_i(sh_p.get(X, 0)))) for X, pl in pools.items()}
    rel = {}
    for X, pl in pools.items():
        why = None
        if not enabled:
            why = 'gate'
        elif step >= pl['due']:
            why = 'due'
        elif hour >= _JIT_DEADLINE_H or step >= _JIT_LAST or d != pl['day']:
            why = 'deadline'
        elif any(v in st['riv'][X] for v in range(pl['start'] + 1, step)):
            why = 'rival'
        elif ex_p.get(X, 0) > 0:
            why = 'next_sell'
        if enabled and _JIT_NTF_YIELD == 'cap' and _jit_ntf_active(X, step, nt):
            if step >= _jit_ntf_dead(step):
                if why in (None, 'due', 'rival'):
                    why = 'deadline'
            elif why in ('due', 'rival'):
                pr = _jit_price(X, _jit_i(inv.get(X, 0)), params)
                if pr is not None and pr < _jit_i(g.get('_NTF_FLOOR', 60), 60):
                    rep['ntf_wait'] += 1
                    why = None
        if why:
            rel[X] = why
    holds = {}
    chain = {}
    skips = []
    if enabled and window:
        for X in _JIT_ITEMS:
            e = ex_p.get(X, 0)
            if e <= 0 or (X in pools and X not in rel):
                continue
            if X in rel and (_JIT_NEXT == 'flush' or (_JIT_NEXT == 'chain' and rel[X] != 'next_sell')):
                continue
            ntfa = _JIT_NTF_YIELD in ('skip', 'cap') and _jit_ntf_active(X, step, nt)
            if ntfa and _JIT_NTF_YIELD == 'skip':
                skips.append((X, 'ntf', {}))
                continue
            u, why, info = _jit_target(st, p, X, step, shops, debts, si, ci, _jit_ntf_dead(step) if ntfa else None)
            if u > step:
                if X in rel and _JIT_NEXT == 'chain':
                    chain[X] = (u, info)
                else:
                    holds[X] = (e, u, info)
            else:
                skips.append((X, why, info))
    for X in chain:
        rel.pop(X, None)
    blank = set(holds) | set(chain) | {X for X in pools if X not in rel}
    new, placed = _jit_build(market, rel, P, blank, prices)
    keep = {X for X in pools if X not in rel or placed.get(X) == 'full'}
    room = None
    if keep or holds or chain:
        dues = [pools[X]['due'] for X in keep] + [h[1] for h in holds.values()] + [c[0] for c in chain.values()]
        room = _jit_room_risk(obs, action, new, p, step, view_r, sh_r, max(dues))
        if not room and _JIT_CASH_GUARD:
            if not _jit_cash_ok(new, obs, p, sh_r, float(obs['farms'][p]['money']), params) \
                    and _jit_cash_ok(market, pobs, p, sh_p, float(pobs['farms'][p]['money']), params):
                room = 'cash'
        if room:
            rep['room_why'][room] = rep['room_why'].get(room, 0) + 1
            if room == 'now' and pools:
                rep['overflow_seen'] += 1
            rep['skip_cash' if room == 'cash' else 'skip_room'] += len(holds) + len(chain)
            holds = {}
            chain = {}
            rw = 'cash' if room == 'cash' else 'room'
            rel = {X: rel.get(X, rw) for X in pools}
            new, placed = _jit_build(market, rel, P, set(), prices)
    touched = set(rel) | set(holds) | set(chain) | set(pools)
    if new != market and not _jit_guard(market, new, touched):
        rep['skip_guard'] += 1
        return action, None
    ex_f = _jit_exec(new, sh_r)
    delta = {X: ex_f.get(X, 0) - ex_p.get(X, 0) for X in _JIT_ITEMS}
    commit = dict(rel=rel, placed=placed, holds=holds, chain=chain, P=P, delta=delta, new=new, ex_p=ex_p, ex_f=ex_f,
                  skips=skips, room=room)
    if new == market:
        return action, commit
    result = dict(action)
    result['market'] = new
    return result, commit


def _jit_commit(obs, st, step, p, c):
    """1) pool state on a copy, swapped in at the end (an exception leaves st untouched); 2) ledgers; 3) telemetry."""
    rep = _JIT_REPORT
    pools = _jit_cp.deepcopy(st['pool'])
    rel_now = set()
    held_now = set()
    inv = obs['market']['inventory']
    prices = obs['market']['prices']
    params = _jit_params(obs)
    d = step // 24
    rows = []
    pk = 0
    for X, why in c['rel'].items():
        pl = pools.get(X)
        if pl is None:
            continue
        how = c['placed'].get(X, 'none')
        q = c['P'].get(X, 0)
        if how == 'full':
            pl['q'] = q
            rows.append(dict(ev='full', step=step, player=p, item=X, q=q, why=why))
            continue
        del pools[X]
        rel_now.add(X)
        rows.append(dict(ev='release', step=step, player=p, item=X, q=q, q0=pl['q0'], why=why, how=how,
                         start=pl['start'], due=pl['due'], quote=_jit_i(prices.get(X, 0)), hold_quote=pl['quote'],
                         lost=max(0, pl['q'] - q), est0=pl['est'], q_pool=pl['q']))
    for X, (u, info) in c['chain'].items():
        pl = pools.get(X)
        if pl is None:
            continue
        e = c['ex_p'].get(X, 0)
        pl['q'] = c['P'].get(X, 0) + e
        pl['q0'] += e
        pl['due'] = u
        pl['est'] += _jit_seq(X, _jit_i(inv.get(X, 0)), e, params)
        held_now.add(X)
        rows.append(dict(ev='chain', step=step, player=p, item=X, q=pl['q'], due=u, info=info))
    for X, (e, u, info) in c['holds'].items():
        est = _jit_seq(X, _jit_i(inv.get(X, 0)), e, params)
        if X in pools:
            pl = pools[X]
            pl['q'] += e
            pl['q0'] += e
            pl['due'] = min(pl['due'], u)
            pl['est'] += est
        else:
            pools[X] = dict(q=e, q0=e, due=u, start=step, day=d, est=est, quote=_jit_i(prices.get(X, 0)))
        held_now.add(X)
        rows.append(dict(ev='hold', step=step, player=p, item=X, q=e, u=u, quote=_jit_i(prices.get(X, 0)), est=est,
                         **info))
    for X, pl in pools.items():
        if X in c['P'] and X not in held_now and c['P'][X] < pl['q']:
            pk += pl['q'] - c['P'][X]
            pl['q'] = c['P'][X]
    st['pool'] = pools
    st['released_now'] |= rel_now
    st['held_now'] |= held_now
    rep['pickup_leak'] += pk
    # 2) ledgers
    try:
        for X, dq in c['delta'].items():
            if dq:
                rep['ledger_fixes'] += _jit_patch_own(p, step, X, dq, c['new'])
    except Exception:
        rep['errors'] += 1
    # 3) telemetry
    try:
        for r in rows:
            ev = r['ev']
            X = r['item']
            if ev == 'hold':
                rep['holds'] += 1
                rep['held_units'] += r['q']
                rep['holds_item'][X] = rep['holds_item'].get(X, 0) + 1
                rep['units_item'][X] = rep['units_item'].get(X, 0) + r['q']
                rep['est_hold'] += r['est']
                if r.get('b') is not None:
                    rep['blocked_cut'] += 1
            elif ev == 'chain':
                rep['chain'] += 1
            elif ev == 'full':
                rep['place_full'] += 1
            elif ev == 'release':
                rep['rel_' + r['why']] = rep.get('rel_' + r['why'], 0) + 1
                rep['place_' + r['how']] = rep.get('place_' + r['how'], 0) + 1
                rep['left_units'] += r['lost']
                rep['hold_len_sum'] += step - r['start']
                if r['q'] > 0:
                    rep['reissues'] += 1
                    rep['reissued_units'] += r['q']
                    est1 = _jit_seq(X, _jit_i(inv.get(X, 0)), r['q'], params)
                    base = r['est0'] * r['q'] / float(max(1, r['q0']))
                    r['est1'] = est1
                    rep['est_release'] += est1
                    rep['est_gain'] += int(round(est1 - base))
            _jit_log(r)
        for X, why, info in c['skips']:
            rep['skip_' + why] = rep.get('skip_' + why, 0) + 1
    except Exception:
        rep['telemetry_errors'] += 1


def _jit_fallback(action, pobs, st):
    """Guard miss / exception while pools are hidden: clamp the parent's SELL orders of every hidden item, in slot order,
    to the stock of the parent's own view (what the parent could sell in its no-hold world), so phantom lots cannot sell
    pool units. The pools stay held; their triggers retry next step."""
    hid = {X for X, q in (st.get('hidden') or {}).items() if q > 0 and X in st['pool']}
    if not hid or not isinstance(action, dict):
        return action
    market = action.get('market')
    if not isinstance(market, list):
        return action
    _JIT_REPORT['fallbacks'] += 1
    try:
        sh = projected_shed(action, FarmView(pobs))
        cap = {X: max(0, _jit_i(sh.get(X, 0))) for X in hid}
    except Exception:
        cap = dict.fromkeys(hid, 0)
    new = list(market)
    changed = False
    for i in range(min(len(new), MAX_ORDERS)):
        o = new[i]
        if _jit_is_sell(o) and o[1] in cap:
            q = max(0, _jit_i(o[2]))
            k = min(q, cap[o[1]])
            cap[o[1]] -= k
            if k < q:
                new[i] = ['SELL', o[1], k] if k > 0 else []
                changed = True
    if not changed:
        return action
    _JIT_REPORT['fb_clamped'] += 1
    out = dict(action)
    out['market'] = new
    return out


def _jit_post(obs, pobs, out, st, step, p):
    """Leak accounting (+ ledger booking) for pools hidden this step, pool telemetry, and the self-clock record of our
    final action."""
    rep = _JIT_REPORT
    sh_r = st.get('sh_r')
    market = (out or {}).get('market') or [] if isinstance(out, dict) else []
    if sh_r is None:
        sh_r = projected_shed(out if isinstance(out, dict) else {}, FarmView(obs))
    if st['pool'] and st['hidden']:
        sh_v = projected_shed(out if isinstance(out, dict) else {}, FarmView(pobs)) if pobs is not obs else sh_r
        ex_r = _jit_exec(market, sh_r)
        ex_v = _jit_exec(market, sh_v)
        for X, pl in list(st['pool'].items()):
            if X not in st['hidden'] or X in st['released_now'] or X in st['held_now']:
                continue
            lk = max(0, ex_r.get(X, 0) - ex_v.get(X, 0))
            if lk > 0:
                rep['leak_units'] += lk
                try:
                    rep['ledger_fixes'] += _jit_patch_own(p, step, X, lk, market)
                    rep['leak_booked'] += lk
                except Exception:
                    rep['errors'] += 1
                pl['q'] = max(0, pl['q'] - lk)
                if pl['q'] <= 0:
                    del st['pool'][X]
    if st['pool']:
        rep['pool_steps'] += 1
        rep['max_pool'] = max(rep['max_pool'], sum(pl['q'] for pl in st['pool'].values()))
    if step >= _JIT_REC_FROM:
        ex = _jit_exec(market, sh_r)
        inv = obs['market']['inventory']
        st['rec'] = dict(step=step, inv={X: _jit_i(inv.get(X, 0)) for X in _JIT_ITEMS},
                         shops=list(obs['town']['unlocked_shops']), own={X: ex.get(X, 0) for X in _JIT_ITEMS},
                         proj={X: max(0, _jit_i(sh_r.get(X, 0))) for X in _JIT_ITEMS}, si=st['si'], ci=st['ci'])


def _jit_abandon(st, why):
    for X, pl in list(st['pool'].items()):
        _JIT_REPORT['abandoned'] += 1
        _JIT_REPORT['abandoned_units'] += pl['q']
        _jit_log(dict(ev='abandon', step=st['step'], item=X, q=pl['q'], why=why))
    st['pool'] = {}


def jit_agent(observation, configuration=None):
    st = None
    pobs = observation
    step = -1
    p = 0
    try:
        step = int(observation['step'])
        p = int(observation['player'])
        st = _JIT_STATE.get(p)
        if st is None or step == 0 or step <= st['step']:
            st = _JIT_STATE[p] = _jit_new_state()
            if step == 0:
                _jit_reset_report()
        st['step'] = step
        st['si'], st['ci'] = _jit_intervals(configuration)
        st['hidden'] = {}
        st['hidden_money'] = 0.0
        st['released_now'] = set()
        st['held_now'] = set()
        st['sh_r'] = None
        if step == 0:
            _jit_open(observation, p, st)
        if step == 1:
            _jit_gate(observation, p, st, configuration)
        live = st['gate'] is True and (globals().get('_NT_D1') or {}).get(p) is not False
        if not live and not st['pool']:
            st['rec'] = None
            st = None
        else:
            _jit_observe(observation, st, step)
            for X, pl in list(st['pool'].items()):
                if pl['day'] != step // 24:
                    _jit_abandon(st, 'day')
                    break
            if st['pool'] and step % 24 == 23:
                _JIT_REPORT['h23_abandon'] += 1
                _jit_abandon(st, 'h23')
            pobs = _jit_parent_obs(observation, st, p)
    except Exception:
        _JIT_REPORT['errors'] += 1
        pobs = observation
        if st is not None:
            try:
                st['hidden'] = {}
                st['hidden_money'] = 0.0
                _jit_abandon(st, 'error')
            except Exception:
                st = None
    action = _JIT_PARENT[0](pobs, configuration)
    if st is None or not isinstance(action, dict):
        return action
    out = action
    commit = None
    try:
        out, commit = _jit_core(observation, pobs, action, st, step, p)
    except Exception:
        _JIT_REPORT['errors'] += 1
        out = action
        commit = None
    if commit is not None:
        try:
            _jit_commit(observation, st, step, p, commit)
        except Exception:
            _JIT_REPORT['errors'] += 1
            _JIT_REPORT['commit_fail'] += 1
            out = action
            commit = None
    if commit is None and st['hidden']:
        try:
            out = _jit_fallback(out, pobs, st)
        except Exception:
            _JIT_REPORT['errors'] += 1
    try:
        _jit_post(observation, pobs, out, st, step, p)
    except Exception:
        _JIT_REPORT['telemetry_errors'] += 1
    return out


jit_agent.telemetry = _JIT_REPORT
