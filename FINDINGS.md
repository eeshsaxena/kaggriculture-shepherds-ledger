# Kaggriculture: research findings

This is the distilled version of the research, written up from the full working log.

## The game, in one paragraph

Kaggriculture is a two player farming simulation: 30 days x 24 hours = 720 steps,
final reward = money in the bank. Each turn an agent issues unit actions (plant,
water, harvest, feed, move, pick up, drop) and market orders (buy seeds / animals /
products, sell products, hire, buy land). The two players share one market whose
price for each product is a pure function of that product's current market
inventory. The competition's final ranking is a Bradley-Terry fit over roughly two
weeks of games played after the deadline, using each team's latest two submissions.
Because Bradley-Terry counts wins, the quantity that matters is win rate, and the
sensitive proxy for it is per-game money margin.

## The one economic fact that governs everything

The shared market never mean-reverts inside a game. `market_price(item, inventory)`
depends only on the current inventory, and inventory only moves through trades and a
small fixed town consumption (each unlocked shop eats 1 to 2 units of its products
every 4 steps; the town center eats 1 of a few products every 24 steps). There is no
daily price recovery.

Three consequences drove every design decision:

1. **Dumping is a weapon, restraint is a gift.** If we hold a lot back to "sell at a
   better price later", the price does not recover, and we have simply let the rival
   sell into clear air. Measured repeatedly: any sell-restraint or deferral lever
   helps the rival 2 to 4 times more than it helps us. This killed a large family of
   intuitive ideas (sale metering, holding for recovery, early-selling to "set" a
   price).

2. **Town demand, not supply, sets the ceiling.** A product with an unlocked shop is
   consumed every 4 steps, so its price stays high (tomato reached ~$244 vs base 60
   in shop-rich worlds); a product with no shop only ever falls (fertilizer has no
   town demand at all and decays from $100 to single digits by the end of the game).
   Producing the right product for the shops that unlock is worth far more than any
   trading cleverness.

3. **Only two kinds of edit reliably helped:** (a) *pure waste* fixes that remove an
   action or purchase that cannot pay back, or that recover value the engine would
   otherwise destroy, and (b) the *JIT sale-delay* in non-twin games against a poorer
   rival (described below), which is the single exception where delaying a sale helps,
   because it is aimed at a specific predictable opponent sale rather than at the
   price curve.

## Approach: a public chassis plus our own layers

The agent is the public "Shepherd's Ledger" tape-replay chassis (routes chosen at
step 144 by the first shops unlocked) with a stack of our own layers appended. Each
layer wraps the previous outermost agent, reads the action it would take, and edits
only a narrow, measured case, falling back to the unedited action on any exception.
This kept every change auditable and independently measurable.

Build lineage of the final pair:

```
FO_B  (base: chassis + FAMTW + FEEDX + twin knob tune)
  -> FOB3   = FO_B + COWBANK + FINHARV v2 + OVERSKIP23 v2 + JIT
  -> FOB3n  = FOB3 with the JIT NTF-yield setting opened up        [final slot 2]
  -> FOB4   = FOB3n + JIT retune (r1) + FCSKIP v2                  [final slot 1]
```

## The layers (our work)

All layer sources are in [`layers/`](layers/). Effects are per-game money margin
versus the parent build, measured on the deterministic panels described under
*Methodology*; "0 flips" means no game changed win/loss.

| Layer | What it does (the measured pure-waste or timing case) |
|---|---|
| `layer_feedx.py` | Skips day 26 to 28 FEED actions on animals that can no longer produce before the game ends. The forfeited wheat stays in inventory and reaches the shed. |
| `layer_cowbank.py` | Skips surplus pre-production cow FEEDs when enough fed-and-cared days are already banked for the cow to mature on time. |
| `layer_finharv_v2.py` | Turns a WATER or PASS on a finished TOMATO or STRAWBERRY tile (one that still has yield and will not produce again) into a HARVEST, recovering a lot the game would leave on the tile. |
| `layer_overskip_v2.py` | At hour 23, drops unit actions that add cargo the day-end auto-drop would destroy (the shed is full and the tail of the inventory is lost), keeping the higher-value items. |
| `layer_famtw.py` | Reclassifies a rival as a "twin" (same public-family code) when the two farms match on census, quadrants, animals and hand counts but differ only by one day-0/1 hire, which otherwise switched off every twin-validated lever. Never edits an action. |
| `layer_jit.py` | The one deferral that works. In non-twin games where the rival is poorer, it records the rival's per-item sale steps over a lookback window and holds our own STRAWBERRY / MILK / WOOL / CARROT / TOMATO lots until just before the rival's predicted next sale of that item, so the rival sells first into the low price and we sell after. Gated, with a room guard, a cash guard, a deadline release, and ledger patching so inner layers stay consistent. |
| `layer_jit_retune_r1.py` | Extends the JIT hold window to step 717 and the horizon to 24 steps, and adds order-aware release placement: a released lot is re-inserted right after the last parent SELL lot of equal-or-greater first-mover value, so it never demotes a more valuable lot in the per-unit market lockstep. |
| `layer_fcskip_v2.py` | FCSKIP. Skips a COLLECT_FERTILIZER at hours 14 to 22 when a tape lookahead of the day's remaining harvests shows the carried cargo will overflow the shed at the day-end drop and the fertilizer (which has no town demand and is nearly worthless late) would be traded away for strawberries or eggs in the destroyed tail. Fertilizer resets nightly, so a skipped collect forfeits exactly one unit. |
| `layer_presell_rejected.py` | Rejected (kept for the writeup). In twin games it sells the tape's next-step lots one step early to beat the identical twin sale. Measured +$17 per twin game but with large two-sided variance and one -$1,900 game, because appending or suppressing an order desynchronizes the ~30 inner layers' ledgers. Not shipped. |

### The two levers that make FOB4 the strongest build

- **JIT retune (r1):** +$23 akmr seat, +$108 top teams on screen; +$102 feel-the-agi,
  +$46 top-5 on confirm; inert on twins (the gate requires a non-twin game), 0 flips.
- **FCSKIP v2:** +$47 akmr, +$79 top teams; +$47 feel-the-agi, +$28 top-5, +$26 field;
  +$30 on 1,036 twin replays with 5 wins gained and none lost, 0 errors.

**FOB4 versus FOB3n overall:** akmr +$68, top teams +$180, feel-the-agi +$151 (1 win
gained), top-5 +$78, public field +$26, twin replays +$30 (5 wins gained, 0 lost),
0 errors on every panel; release gate clean (timing, cross-episode leak, crash fuzz).

## What we proved does not work (negative results)

These are as useful for a writeup as the wins; each was measured, not assumed.

- **Structural production gaps are not layerable.** The teams above ~2,600 win on
  build structure: geese and eggs sized to egg shops from day 0, tomatoes sized to
  pizza/market demand, a 4th quadrant bought by day 10 to 14. Our tape chassis freezes
  the herd and crop plan by day 11. Every attempt to graft structure on with a layer
  (geese-for-sheep swaps, herd swaps, route-table swaps, eager fertilizer) measured
  negative, because it fought the chassis' own routing. This is the real ceiling and
  it cannot be closed after the route is chosen.

- **Sell timing against the price curve.** Sale metering (1 to 3 units per step),
  holding for price recovery, early dumping to set a price, and front-running the
  rival's generic sales were all negative or zero. The only positive timing lever is
  JIT, which targets a specific predicted opponent sale, not the curve.

- **Wheat sell-into-buy.** Adaptive rivals buy 100 to 300 wheat per day, which lifts
  the price. Selling our wheat right after those buys looked promising but the lift is
  transient (the rival sells the lot back the next step) and the realistic gain was a
  median of $0 per game.

- **Five pure-waste lenses came up empty** after engine-exact audits: end-of-game
  stranded stock (the chassis already liquidates everything by step 718), idle labour
  (no wages, no idle hands), rejected market orders (0 failures that cost anything),
  animal and crop production lost to caps (shed-room-bound, already handled), and
  narrow-loss execution errors (the losses are structural, not execution bugs).

- **Twin pre-sell** (above): a real +$17 per twin game but a butterfly; rejected.

## Methodology (how every number above was obtained)

The scripts are in [`harness/`](harness/) and [`analysis/`](analysis/).

- **Determinism.** The agent has a wall-clock budget, so the same agent differs run to
  run. Every evaluation runs with `PYTHONHASHSEED=0` and a monkeypatched
  `time.perf_counter` (a fixed 5 ms per call), so results are reproducible and two
  builds differ only because of their code. See the top of any `top_eval_det*.py`.

- **Pinned-world seat substitution panels.** `top_eval_det*.py` replays a recorded
  top-team or reference game, puts the candidate in one seat, and pins the opponent's
  recorded tape, the recorded shop-unlock sequence, and the opponent's weed spawns, so
  the only variable is the candidate's play. Panels: `detK1` (a strong reference
  opponent's seat), `det6x` (top teams), `detA` (one strong adaptive opponent),
  `det5` (top-5 teams).

- **Live twin replays.** `replay_eval_det.py` replays ~1,036 of our own recorded live
  games where the rival ran the same public-family code, with the candidate in our
  seat and the rival's recorded tape fixed. Twin margins are tight (standard deviation
  ~4,100, about a quarter within +/-$1,000), so a +$300 twin-side gain flips games;
  this is the most sensitive panel for win flips. Caveat: the fixed rival tape cannot
  react, so rival-reactive effects are not captured.

- **Public field gauntlet.** `gauntlet_det.py` plays the candidate against a field of
  public agents on fresh seeds (seat-symmetric, so one seat per pairing).

- **Single-game trace.** `trace_one.py` replays one pinned game and returns the full
  per-step state plus every layer's telemetry, used to measure the exact waste a lever
  targets before building it.

- **Release gate.** `gate_pub.py` checks per-step timing (first-call and p99 latency),
  cross-episode state leakage (one loaded copy vs a fresh copy per episode, same seeds)
  and crash-fuzz robustness on malformed observations. `gate_leak_det.py` is a
  deterministic (fake-clock) version of the leak check, because the timing-based one is
  noisy under machine load.

- **Comparison.** `re_cmp.py` (twin panel, by win flips) and `nw_cmp.py` (pinned panel
  and gauntlet) report, per candidate versus a base: games, changed games, mean margin
  with a 2-sigma band, wins versus base, and loss->win / win->loss flip lists.

- **Data collection.** `list_live.py`, `fetch_compact.py`, `record.py` and
  `loss_report.py` pull our live episodes, compact them to seed plus both action
  tapes, replay them exactly to recover per-player executed market units and per-day
  money and census, and attribute losses by product.

- **Measurement discipline (hard-won).** Mirror panels (a fork played against an
  identical fork) are invalid: identical forks tie exactly, so any perturbation
  "wins" by stealing from its twin. Everything is measured against a different
  opponent, on an absolute bank and win-rate basis, with a disjoint confirmation
  block. Offline panel wins also do not perfectly predict live rank, so the final
  decision always weighted the live twin replays and the public field most heavily.

## Final submissions

| Agent | Submission | Submitted (UTC) | Build |
|---|---|---|---|
| shepFOB4 | 56719668 | 2026-09-30 21:56 | FOB3n + JIT retune r1 + FCSKIP v2 (the strongest build) |
| shepFOB3n | 56716285 | 2026-09-30 18:52 | FO_B + COWBANK + FINHARV v2 + OVERSKIP23 v2 + JIT |

Both passed the release gate (timing, cross-episode leak, crash fuzz) and validated
with zero errors on every panel.
