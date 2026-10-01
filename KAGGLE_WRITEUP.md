# 322nd Place Solution

### A replay chassis plus measured pure-waste and sale-timing layers, and why our offline proxy lied to us

**Kaggriculture** · Solution Writeup · 322nd place (Silver) · Oct 1, 2026

Thanks to the hosts for a genuinely unusual competition. Most Kaggle competitions are
static: there is a fixed test set and you push a score up. Kaggriculture is a live
two-player economy judged by a Bradley-Terry fit over games played after the deadline,
and that difference turned out to be the whole story of our solution, including its
biggest mistake. I'll tell it honestly, because the negative results here are more
useful than the wins.

When I started, the public "Shepherd's Ledger" tape-replay chassis was already the
strongest shared baseline. Rather than rewrite a 25k-line agent, I decided to treat it
as fixed and ask a narrower question: given a strong replay agent, which small,
auditable edits actually move win rate in this economy? Every change would be one
*layer*, appended to the agent, wrapping the previous behaviour, reading the action it
was about to take and editing only one narrow, measured case, falling back to the
original action on any exception. That way every idea could be turned on or off and
measured in isolation.

## Overview of the approach

The final agents are the Shepherd's Ledger chassis (routes are chosen at step 144 from
the shops unlocked so far) plus a stack of our own layers. The two submitted agents:

- **shepFOB4**: chassis + FAMTW + FEEDX + COWBANK + FINHARV + OVERSKIP23 + JIT (+ retune) + FCSKIP
- **shepFOB3n**: the same without the last two layers

The research split cleanly into three parts: (1) understanding the market, which
explained why most intuitive levers are actively harmful; (2) building the handful of
layers that survived measurement; and (3) a deterministic evaluation harness strong
enough to tell a real $30/game gain from noise. I'll go through each, then the lesson I
wish I'd learned a week earlier.

## The one economic fact that governs everything

The shared market never mean-reverts inside a game. The price of a product is a pure
function of its current market inventory, and inventory only changes through trades and
a small fixed town consumption (each unlocked shop eats 1 to 2 of its products every 4
steps; the town center eats a few products every 24 steps). There is no daily price
recovery.

This single fact has a brutal consequence: **holding a sale back does not get you a
better price later, it just lets the opponent sell into clear air.** I measured this
over and over, and every sell-restraint or deferral idea helped the opponent 2 to 4
times more than it helped us. Sale metering (dripping 1 to 3 units per step), holding
for recovery, early-dumping to "set" a price: all negative. In this game, dumping is a
weapon and restraint is a gift to your opponent.

The second half of the fact is that **town demand, not supply, sets the ceiling.** A
product with an unlocked shop is consumed on a schedule, so its price holds (tomato
reached ~$244 against a base of 60 in shop-rich worlds); a product with no shop only
ever falls (fertilizer has no town demand at all and decays to single digits by the end
of the game). Producing the right thing for the shops that unlock is worth more than any
trading cleverness, and that is exactly the part a layer on a frozen route cannot fix.

So only two kinds of edit were ever going to work: pure-waste fixes, and one very
specific kind of deferral.

## The layers that worked

### Pure-waste fixes

These remove an action or purchase that cannot pay back, or recover value the engine
would otherwise destroy. They are safe almost by definition, they only ever reclaim
something that was being thrown away.

- **FEEDX** skips day 26 to 28 feeds on animals that can no longer produce before the
  game ends. The wheat that would have been spent stays in inventory and reaches the
  shed.
- **COWBANK** skips surplus pre-production cow feeds once enough fed-and-cared days are
  already banked for the cow to mature on time.
- **FINHARV** turns a wasted WATER or PASS on a finished tomato or strawberry tile into
  a HARVEST, collecting a lot the agent was about to leave on the tile.
- **OVERSKIP23** drops hour-23 actions that add cargo the nightly auto-drop would
  destroy (shed full, tail of the inventory lost), keeping the higher-value items.
- **FCSKIP** was the nicest of these. Fertilizer has no town demand, so late in the game
  it is nearly worthless, yet the agent keeps collecting it, and at the day-end drop that
  worthless fertilizer displaces strawberries and eggs out of a full shed. FCSKIP does a
  tape lookahead of the day's remaining harvests, and when it sees the shed will overflow
  it skips the fertilizer collect so the valuable product survives the drop. Fertilizer
  resets nightly, so a skipped collect forfeits exactly one unit. Measured +$47/game on
  the top-team panel and +$30 across 1,036 twin replays with 5 wins gained and none lost.

### JIT: the only deferral that helps

The one exception to "never hold a sale" is to hold it against a *specific predicted
opponent sale* rather than against the price curve. In non-twin games where the opponent
is poorer, JIT records the opponent's per-item sale steps over a lookback window and
holds our own strawberry / milk / wool / carrot / tomato lots until just before the
opponent's predicted next sale of that item. The opponent sells first into the low
price, then we sell after. It is gated, with a room guard, a cash guard, a deadline
release, and ledger patching so the inner layers stay consistent.

A later retune extended the hold window and added order-aware release placement: when a
held lot is released, it is re-inserted right after the last existing sale lot of
equal-or-greater value, so it never demotes a more valuable lot in the per-unit market
lockstep. That detail alone was worth ~+$100/game on the top-team panel.

**shepFOB4 vs shepFOB3n**, on the offline panels: akmr seat +$68/game, top teams +$180,
feel-the-agi +$151 (1 win gained), top-5 +$78, public field +$26, 1,036 twin replays
+$30 (5 wins gained, 0 lost), 0 errors everywhere, clean release gate.

## The validation harness

The agent has a wall-clock budget, so the same agent gives different results run to run.
Everything therefore runs with a fixed clock and `PYTHONHASHSEED=0`, so two builds differ
only because of their code. On top of that:

- **Pinned-world seat substitution:** replay a recorded top-team game, drop the candidate
  into one seat, and pin the opponent's tape, the shop-unlock sequence and the weeds, so
  the candidate's play is the only variable.
- **Live twin replays:** ~1,036 of our own recorded live games where the opponent ran the
  same public-family code, candidate in our seat, opponent tape fixed. These are the most
  sensitive panel for win flips, since twin margins are tight.
- **Public field gauntlet** on fresh seeds.
- **Release gate:** per-step latency, cross-episode state leakage (one loaded copy vs a
  fresh copy per episode on the same seeds), and crash fuzz on malformed observations.

A hard-won measurement note: mirror panels (a fork against an identical fork) are
invalid, identical forks tie exactly, so any perturbation "wins" by stealing from its
twin. Everything was measured against a *different* opponent, on absolute bank and
win-rate, with a disjoint confirmation block.

## What did not work (the useful part)

- **Any sale timing against the price curve:** metering, holding for recovery,
  front-running generic opponent sales. All negative or zero.
- **Selling wheat into an adaptive opponent's buys.** Opponents who buy 100 to 300 wheat
  per day lift the price, so selling right after them looked promising, but the lift is
  transient (they sell the lot back next step) and the realistic gain was a median of $0.
- **Grafting production structure onto a frozen route.** The top teams win on structure:
  geese and eggs sized to egg shops from day 0, tomatoes sized to demand, a fourth
  quadrant by day 10. Our route freezes the herd and crop plan by day 11, and every
  attempt to change it with a layer (herd swaps, geese-for-sheep, route-table swaps,
  eager fertilizer) fought the chassis and measured negative. This is the real ceiling.
- **Five separate pure-waste lenses that came up empty** after engine-exact audits:
  end-game stranded stock, idle labour, rejected market orders, production lost to caps,
  and narrow-loss execution errors. In each case the chassis already handled it, or the
  loss was structural rather than an execution bug.
- **A twin one-step pre-sell lever** that measured +$17/twin game but turned out to be a
  butterfly: appending or suppressing one order desynchronized ~30 inner layers' ledgers
  and produced one -$1,900 game. Rejected.

## The lesson I'd most want to pass on: our offline proxy did not predict live rank

This is the mistake, and it is the most important paragraph here.

Every layer above was validated on the deterministic offline panels, and every step in
our chain measured as an improvement over its parent. But the offline panels replay
*fixed* opponent tapes, and the gains I was chasing were small ($6 to $180 per game)
against a live game-to-game swing of around $4,000. On the live ladder, the line
actually drifted the wrong way:

| Agent | Live rating |
|---|---|
| shepFK | 2359 |
| shepFL | 2328 |
| shepFN | 2236 |
| shepFM | 2228 |
| shepFOB3n (submitted) | 2188 |
| shepFOB4 (submitted) | 2129 |

Our *earlier* agents had the highest live ratings. The later, offline-validated agents
scored lower. The small offline improvements were real against a static tape and too
small and too static to climb a reactive ladder. By the measure that actually resembles
the final Bradley-Terry ranking, continuing to iterate past shepFK/shepFL did not help,
and probably cost us a little.

If I ran this again I would weight live-ladder evidence far above offline panel margins,
keep the pure-waste fixes (those were sound), and stop iterating the moment the measured
per-game gain dropped below the live noise floor. On a live-judged competition, your
offline harness has to be validated against live outcomes, not trusted because it is
precise.

## Code

Full code, both agents, every layer's source, the evaluation harness, and the detailed
findings: **https://github.com/eeshsaxena/kaggriculture-shepherds-ledger**

Thanks to the Shepherd's Ledger authors for the base chassis, and to the hosts and the
community. 322nd of 10,246 and a Silver, and a clear idea of what I'd do differently.
