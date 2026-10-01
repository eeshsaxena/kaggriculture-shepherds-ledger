# 322nd Place Solution

### A replay chassis, a stack of small layers, and a lesson about trusting the wrong numbers

**Kaggriculture** · Solution Writeup · 322nd place (Silver) · Oct 1, 2026

First, thanks to the hosts. This one is different from most Kaggle competitions and that
difference ended up being the whole story for me. There is no fixed test set here. You
submit agents, they play each other on a live ladder, and the final rank comes from a
Bradley-Terry fit over games played after the deadline. I didn't fully respect what that
meant until late, and it cost me, so I'm going to be honest about that part too.

I'll say upfront that I didn't build an agent from scratch. The public "Shepherd's
Ledger" tape-replay chassis was already the strongest thing anyone was sharing, and
rewriting 25,000 lines to maybe match it felt like the wrong bet. So I took it as fixed
and asked a smaller question instead: given a strong replay agent, what small edits
actually move win rate in this economy? Every idea became one *layer*, bolted onto the
agent, wrapping whatever was underneath, looking at the action it was about to take and
changing only one specific thing. If an idea didn't survive measurement, I ripped the
layer back out. That kept everything honest and testable.

## Overview

The final agents are the chassis plus a stack of these layers. Picture it as an onion:
the chassis sits at the bottom and makes a decision, then each layer gets a chance to
tweak that decision on its way out (see the diagram below). The two I submitted were
`shepFOB4` (the full stack) and `shepFOB3n` (the same thing minus the last two layers).

![The agent: one chassis, a stack of small layers](https://raw.githubusercontent.com/eeshsaxena/kaggriculture-shepherds-ledger/master/figures/architecture.png)

The work really had three parts. First, understanding the market, which is what told me
most of my "clever" ideas were actually hurting me. Second, the handful of layers that
survived. Third, a test harness good enough to tell a real $30-per-game gain from pure
noise. I'll walk through each, and then the mistake.

## The one thing you have to understand about the market

The market never recovers inside a game. A product's price depends only on how much of
it is currently sitting in the market, and that number only moves when someone trades or
when the town eats a little on a fixed schedule. There's no "the price will bounce back
tomorrow."

Once that clicked, a lot of my instincts turned out to be backwards. If I hold a lot
back to sell it later at a better price, the price doesn't go up, I've just stepped
aside and let my opponent sell into empty space. I tested this more times than I'd like
to admit, and it was always the same answer: holding back helps the opponent two to four
times more than it helps me. In this game, dumping is a weapon and patience is a gift to
the other player.

The flip side is that demand, not supply, sets the ceiling. If a shop for a product
unlocks, the town keeps buying it and the price stays up (I saw tomato sit around $244
against a base of 60 in the right world). If no shop unlocks for it, the price only ever
falls, fertilizer has no town demand at all and rots down to almost nothing by the end.
So the thing that actually wins games is producing the right stuff for the shops you
draw, and that is exactly the decision the chassis locks in early, before any of my
layers get a vote. More on that later, it's the ceiling I couldn't break.

So realistically only two kinds of edit were ever going to help: fixing pure waste, and
one very particular kind of patience.

## The layers that actually worked

**Pure-waste fixes.** These are the safe ones, they only ever grab back something the
agent was about to throw away.

- *FEEDX* stops feeding animals in the last few days when they can't produce again
  anyway. The wheat you'd have spent just stays with you.
- *COWBANK* stops over-feeding a cow once it's already banked enough days to mature on
  time.
- *FINHARV* harvests a finished crop the agent was about to walk past and leave on the
  tile.
- *OVERSKIP23* notices when the shed is full and the nightly auto-drop is about to
  destroy the tail of your cargo, and drops the low-value stuff instead of the good stuff.
- *FCSKIP* is my favorite of the bunch. Fertilizer is nearly worthless late (no shop
  ever buys it), but the agent keeps dutifully collecting it, and then at the day-end
  drop that junk fertilizer shoves actual strawberries and eggs out of a full shed. So
  FCSKIP looks ahead at the rest of the day's harvest, and if it can see the shed will
  overflow, it just skips the fertilizer pickup so the valuable stuff survives.
  Fertilizer resets every night anyway, so you lose exactly one unit of nothing. Worth
  about +$47 a game against the top teams and +$30 across a thousand twin replays, with
  five games flipped from loss to win and none the other way.

**JIT, the one time patience pays.** The exception to "never hold a sale" is when you're
not fighting the price curve, you're timing a specific opponent. In games against a
poorer opponent, JIT watches when they tend to sell each product, and holds our matching
lot until just before their next predicted sale. They sell first into the low price, and
then we sell. It's carefully fenced in (room check, cash check, a hard deadline to dump
everything, and some bookkeeping so the inner layers don't get confused). A later tweak
also made sure that when a held lot finally gets released, it slots in ahead of our own
lower-value sales rather than behind them, which sounds tiny but was worth about +$100 a
game on its own.

Put together, `shepFOB4` beat `shepFOB3n` on every panel I had: +$68 a game in one
seat, +$180 against the top teams, +$151 against the strongest adaptive opponent, +$78
on the top-5 panel, +$26 on the public field, and +$30 across the twin replays with five
more wins and zero new losses. Clean on the release gate too.

## How I measured things

The agent has a time budget, which means it isn't even deterministic, run it twice and
you get two answers. So everything ran with a frozen clock and a fixed hash seed, so two
builds could only differ because of their code. On top of that I had a few panels:
replaying recorded top-team games with the opponent pinned and my agent dropped into one
seat; replaying about a thousand of my own past games where the opponent was running the
same public code (the most sensitive test, since those margins are razor-thin); a
gauntlet against public agents on fresh seeds; and a release gate checking speed, memory
leaks between games, and that malformed inputs don't crash it.

One trap worth mentioning: testing a fork against an identical copy of itself is
meaningless. Two identical agents tie exactly, so any change "wins" purely by stealing
from its own twin. Everything had to be measured against a genuinely different opponent.

## What didn't work (the useful half)

- Any kind of sale timing against the price curve, metering it out, holding for a
  bounce, front-running generic sales. All flat or negative.
- Selling wheat right after an opponent's big wheat buys. Looked great, because their buy
  lifts the price, but the lift is gone a step later when they sell it back. Median gain:
  zero.
- Trying to bolt better production onto the frozen route. The top teams win on structure,
  more geese in egg worlds, tomatoes sized to demand, a fourth plot of land early, and
  my route is locked by day 11. Every swap I tried fought the chassis and lost. This is
  the real ceiling and no layer gets past it.
- Five separate "surely there's waste here" investigations that turned up nothing after I
  actually traced the engine: end-game leftovers, idle workers, rejected orders, capped
  production, narrow losses. Either the chassis already handled it or the loss was
  structural, not a bug.
- A twin pre-sell trick that measured +$17 a game but was a landmine, nudging one order
  desynced about thirty inner layers and produced a single -$1,900 blowup. Cut it.

## The part I got wrong

Here's the honest bit, and it's the thing I'd actually want someone to take away.

Every layer above passed my offline panels, and every version beat the one before it.
But those panels replay *fixed* opponents, and the gains I was chasing were small,
single or double digits of dollars per game, against a live swing of around four
thousand. On the live ladder, the thing I was optimizing went the wrong way (see the
chart below).

![Live rating across the lineage: offline said better, live said worse](https://raw.githubusercontent.com/eeshsaxena/kaggriculture-shepherds-ledger/master/figures/live_vs_offline.png)

My *earlier* agents had my best live ratings. shepFK sat at 2359 and shepFL at 2328, and
then everything I "improved" after that came in lower, down to the pair I actually
submitted at 2188 and 2129. The offline wins were real, they just didn't mean anything
on a reactive ladder. I was polishing a number that didn't predict the one that counts.

If I did this again I'd trust the live signal way more than my offline panels, keep the
pure-waste fixes (those were genuinely fine), and stop the moment a change's per-game
edge dropped under the live noise. On a live-judged competition your offline harness has
to earn your trust by matching live results, and mine quietly stopped doing that while I
kept believing it.

Still, 322nd out of 10,246 and a Silver, and I came out of it actually understanding the
game. I'll take it.

## Code

Everything is here, both agents, every layer, the full harness, and the detailed
numbers: **https://github.com/eeshsaxena/kaggriculture-shepherds-ledger**

Thanks to the Shepherd's Ledger authors for the base, and to the hosts and everyone in
the discussions.
