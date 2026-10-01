
# ---------------------------------------------------------------------------
# W4 jit lens, REVIEW FIX r1 (2026-09-30): order-aware JIT release placement (appended after the jitlh knobs).
# ENGINE (_process_market 544-628): orders run slot by slot; inside slot i both players' slot-i SELL units alternate in
#   per-unit lockstep, so a lot in an earlier slot sells ENTIRELY before the rival's same-item lot in a later slot.
# DEFECT: _jit_place put every released pool at slot 0 after the leading HIREs ('grow' also moved the parent's lot
#   there), which pushed every other parent SELL lot of that step down one slot, whatever its value. Trace agi
#   114418974/1 step 646 (jitlh_v1): a CARROT pool (price slope ~$0) and a WOOL 2 pool pushed our STRAWBERRY 20 from
#   slot 0 to slot 2, behind the rival's slot-1 STRAWBERRY 11: our money -$383, the rival +$402 (the whole game loss).
#   Longer holds (horizon 24, window to 717) put more releases on steps where the parent sells steep lots.
# FIX: first-mover value of a lot v = qty * (price(inv) - price(inv + 10)) at the step's opening inventory (engine curve,
#   the game's params). Inside the sell run after the leading HIREs (contiguous SELL / free orders up to the first HIRE /
#   BUY / other order), the released lot goes right after the LAST parent SELL lot with v >= the pool's v, so no lot
#   worth more is demoted; it still precedes every later HIRE / BUY (its revenue funds them as before). A free slot at
#   that position is reused in place (nothing shifts); 'grow' never moves the grown lot later than the parent's own slot.
#   A position outside the executed window, the merge2 / full cases and any exception use the original _jit_place.
#   The window guard, cash guard and room guard of JIT are unchanged. Twin games: JIT is off, nothing changes.
# ---------------------------------------------------------------------------
_WPL_PARENT = ([v for v in list(globals().values()) if callable(v)][-1],)
_WPL_ORIG = (_jit_place,)
_WPL_CTX = {'obs': None}


def _wpl_new_report():
    return {'calls': 0, 'moved': 0, 'at_lead': 0, 'how': {}, 'orig': 0, 'errors': 0}


_WPL_REPORT = _wpl_new_report()


def _wpl_v(X, q, inv, params):
    x = _jit_i(inv.get(X, 0))
    return max(0, _jit_i(q)) * max(0, _r37_market_price(X, x, params) - _r37_market_price(X, x + 10, params))


def _wpl_pos(new, lead, vpool, inv, params):
    """Index right after the last SELL lot with v >= vpool in the sell run that starts at lead (lead when none)."""
    win = min(len(new), MAX_ORDERS)
    pos = lead
    k = lead
    while k < win:
        o = new[k]
        if _jit_free(o):
            k += 1
            continue
        if _jit_is_sell(o):
            if _wpl_v(o[1], o[2], inv, params) >= vpool:
                pos = k + 1
            k += 1
            continue
        break
    return pos


def _wpl_place(market, item, q, prices):
    rep = _WPL_REPORT
    rep['calls'] += 1
    try:
        obs = _WPL_CTX.get('obs')
        inv = obs['market']['inventory']
        params = obs['market'].get('params')
        new = [list(o) if isinstance(o, (list, tuple)) else o for o in market]
        lead = _jit_lead(new)
        win = min(len(new), MAX_ORDERS)
        j = next((i for i in range(lead, win) if _jit_is_sell(new[i], item)), None)
        if j is not None:
            o = new.pop(j)
            qq = max(0, _jit_i(o[2])) + q
            pos = min(j, _wpl_pos(new, lead, _wpl_v(item, qq, inv, params), inv, params))
            new.insert(pos, ['SELL', item, qq])
            how = 'grow'
        else:
            pos = _wpl_pos(new, lead, _wpl_v(item, q, inv, params), inv, params)
            if pos >= MAX_ORDERS:
                rep['orig'] += 1
                return _WPL_ORIG[0](market, item, q, prices)
            if pos < win and _jit_free(new[pos]):
                new[pos] = ['SELL', item, q]
                how = 'slot'
            elif len(new) < MAX_ORDERS:
                new.insert(pos, ['SELL', item, q])
                how = 'insert'
            else:
                k = next((i for i in range(pos, win) if _jit_free(new[i])), None)
                if k is None:
                    rep['orig'] += 1
                    return _WPL_ORIG[0](market, item, q, prices)
                new.pop(k)
                new.insert(pos, ['SELL', item, q])
                how = 'slot'
        if pos >= MAX_ORDERS or not _jit_is_sell(new[pos], item):
            rep['orig'] += 1
            return _WPL_ORIG[0](market, item, q, prices)
        rep['how'][how] = rep['how'].get(how, 0) + 1
        if pos > lead:
            rep['moved'] += 1
        else:
            rep['at_lead'] += 1
        return new, how
    except Exception:
        rep['errors'] += 1
        return _WPL_ORIG[0](market, item, q, prices)


_jit_place = _wpl_place


def wpl_agent(observation, configuration=None):
    try:
        if int(observation['step']) == 0:
            _WPL_REPORT.clear()
            _WPL_REPORT.update(_wpl_new_report())
        _WPL_CTX['obs'] = observation
    except Exception:
        _WPL_CTX['obs'] = None
    return _WPL_PARENT[0](observation, configuration)


wpl_agent.telemetry = _WPL_REPORT
