# 322nd / 10,246 (Silver): what moved win rate in Kaggriculture, and what didn't

Final result: **322nd of 10,246 teams, Silver medal.** Final pair `shepFOB4` and
`shepFOB3n`, both the public "Shepherd's Ledger" tape-replay chassis with a stack of
our own layers on top.

Code, agents, and the full methodology: **https://github.com/eeshsaxena/kaggriculture-shepherds-ledger**

This is a write-up of what we learned measuring layer after layer on a replay agent,
including the one lesson I'd most want another competitor to take away, which is a
negative result about our own process.

## The economic fact that governs the whole game

The shared market never mean-reverts inside a game. `market_price(item, inventory)`
depends only on current inventory, and inventory moves only through trades and a small
fixed town consumption. There is no daily price recovery.

So **holding a sale back does not get you a better price later, it just lets the
opponent sell into clear air.** We measured this many times: essentially every
sell-restraint or deferral idea helps the opponent 2 to 4 times more than it helps us.
That one fact kills a whole family of intuitive levers (sale metering, holding for
recovery, early-dumping to "set" a price).

Only two kinds of edit reliably helped:

1. **Pure-waste fixes:** remove an action or purchase that cannot pay back, or recover
   value the engine would otherwise destroy (unsellable end-game feeds, finished crop
   lots left on the tile, hour-23 cargo the day-end drop destroys, fertilizer collected
   only to be thrown away at overflow).
2. **One targeted deferral (JIT):** in non-twin games against a poorer opponent, hold a
   lot until just before the opponent's *predicted* next sale of that item, so the
   opponent sells first into the low price and we sell after. This is the only
   deferral that works, because it targets a specific predicted opponent sale rather
   than fighting the price curve.

The structural way the top teams win (production sized to shop demand from day 0, a
fourth quadrant, more geese and tomatoes) is set by the chosen route and cannot be
retrofitted by a layer. That is the real ceiling, and we confirmed every attempt to
graft structure on measured negative.

## The most important lesson: our offline proxy did not predict live rank

This is the part I'd stress to anyone running a replay/lever approach on a live ladder.

We validated each new layer on deterministic offline panels: recorded top-team games
with the opponent tape pinned, ~1,036 of our own live games replayed as "twins", and a
public-agent gauntlet, all with a fixed clock and `PYTHONHASHSEED=0` so two builds
differ only by code. Every step in our chain measured as an improvement over its parent.

On the **live ladder, the line drifted the other way:**

| Agent | Live rating |
|---|---|
| shepFK | 2359 |
| shepFL | 2328 |
| shepFN | 2236 |
| shepFM | 2228 |
| shepFOB3n (final) | 2188 |
| shepFOB4 (final) | 2129 |
| shepFO_B | 2114 |

Our earlier agents (FK, FL) had the **highest** live ratings, and the later,
offline-validated agents scored lower. The reason: the offline panels replay *fixed*
opponent tapes, and the gains we were chasing were small ($6 to $180 per game) against
a live game-to-game swing of around $4,000. Real improvements against a static tape,
too small and too static to climb a reactive ladder.

If I ran this again, I would weight live ladder evidence far more heavily than offline
panel margins, and I would stop iterating once the per-game gains dropped below the live
noise floor. The pure-waste fixes were sound; the micro-levers past a certain point were
measuring something that did not exist on the live board.

## Methodology (reusable)

The repo has the full harness. Briefly:

- **Determinism:** fixed clock + `PYTHONHASHSEED=0`, so a candidate is reproducible and
  only code differences show up.
- **Pinned-world seat substitution:** replay a recorded top-team game, drop the
  candidate into one seat, pin the opponent's tape, the shop-unlock sequence, and the
  weeds.
- **Live twin replays:** our own recorded games where the rival ran the same
  public-family code; the most sensitive panel for win flips.
- **Public field gauntlet** on fresh seeds.
- **Release gate:** per-step latency, cross-episode state leakage, crash fuzz on
  malformed observations.

## What we proved does not work (so you don't have to)

- Sell timing against the price curve (metering, holding, front-running generic sales).
- Selling wheat into an adaptive rival's buys (the price lift is transient; median gain $0).
- Grafting production structure onto a frozen route (every herd/crop/route swap negative).
- Five separate pure-waste lenses that came up empty after engine-exact audits
  (end-game stranded stock, idle labour, rejected orders, production lost to caps,
  narrow-loss execution errors): the chassis already handled them or the losses were
  structural, not execution bugs.
- A twin one-step pre-sell lever (+$17/twin game, but a butterfly: appending or
  suppressing an order desynchronized ~30 inner layers' ledgers, with one -$1,900 game).

Full detail, every layer's source, and the exact numbers are in the repo's
[`FINDINGS.md`](https://github.com/eeshsaxena/kaggriculture-shepherds-ledger/blob/master/FINDINGS.md).

Happy to answer questions. Thanks to the Shepherd's Ledger authors for the base chassis.
