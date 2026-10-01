# Kaggriculture: Shepherd's Ledger agents and research

Research, agents, and evaluation harness for the Kaggle **Kaggriculture** competition,
a two player farming-simulation ladder whose final ranking is a Bradley-Terry fit over
games played after the deadline on each team's latest two submissions.

The agents are built on the public "Shepherd's Ledger" tape-replay chassis, with a
stack of our own layers appended on top. The research is about which edits to a
replay agent actually move win rate in a shared-market economy, and, just as much,
which intuitive edits provably do not.

**Start here:** [`FINDINGS.md`](FINDINGS.md) is the distilled write-up of what we
learned.

## Result

**322nd of 10,246 teams (top ~3.1%), Silver medal.** A write-up for the Kaggle
discussion forum is in [`WRITEUP.md`](WRITEUP.md); the distilled research is in
[`FINDINGS.md`](FINDINGS.md).

## Headline finding

The shared market never mean-reverts inside a game, so holding a sale back does not
get a better price later, it just lets the opponent sell into clear air. We measured
that essentially every sell-restraint idea helps the opponent 2 to 4 times more than
it helps us. Only two kinds of change reliably helped:

1. **Pure-waste fixes:** remove an action or purchase that cannot pay back, or recover
   value the engine would otherwise destroy.
2. **One targeted deferral (JIT):** in non-twin games against a poorer opponent, hold
   a lot until just before the opponent's *predicted* next sale of that item, so the
   opponent sells first into the low price.

The structural way the top teams win (production sized to shop demand from day 0, a
fourth quadrant, more geese and tomatoes) is set by the chosen route and cannot be
retrofitted by a layer. That is the real ceiling.

## Final submissions

| Agent | Submission | Build |
|---|---|---|
| **shepFOB4** | 56719668 | FOB3n + JIT retune + FCSKIP v2 (strongest; see FINDINGS) |
| **shepFOB3n** | 56716285 | FO_B + COWBANK + FINHARV v2 + OVERSKIP23 v2 + JIT |

shepFOB4 beats shepFOB3n on every evaluation panel (akmr seat +$68/game, top teams
+$180, feel-the-agi +$151, top-5 +$78, public field +$26, 1,036 live twin replays +$30
with 5 wins gained and none lost), with 0 errors and a clean release gate.

## Repository map

```
WRITEUP.md           Kaggle discussion write-up (result + lessons)
FINDINGS.md          Distilled research write-up (read this first)
agents/              The two final submitted agents
layers/              Our own layer implementations (the substance of the work)
harness/             Deterministic evaluation panels, gauntlet, release gate, trace
analysis/            Live-data collection and loss-attribution scripts
```

Each file under `layers/` is one appended layer; `layers/layer_presell_rejected.py`
is a measured-but-rejected lever kept for the write-up. `harness/` holds the
deterministic panels (`top_eval_det*.py`, `replay_eval_det.py`, `gauntlet_det.py`),
the single-game trace (`trace_one.py`), the release gate (`gate_pub.py`,
`gate_leak_det.py`), and the shell wrappers used to run them.

## Reproducing a measurement

The harness assumes the `kaggle_environments` Kaggriculture environment and a set of
recorded game tapes (compact seed + both action tapes), which are not committed here
because they are large and derived from the public Kaggle replays. With those in
place, every panel runs deterministically:

```bash
# twin replays: candidate vs recorded rival tapes, by win flips
PYTHONHASHSEED=0 python harness/replay_eval_det.py out.jsonl <nproc> <subs> base.py cand.py
python analysis/re_cmp.py out.jsonl base.py

# pinned top-team panel
PYTHONHASHSEED=0 python harness/top_eval_det6x.py out.jsonl <nproc> <maxgames> base.py cand.py
python analysis/nw_cmp.py base.py out.jsonl

# release gate (timing / cross-episode leak / crash fuzz)
PYTHONHASHSEED=0 python harness/gate_pub.py cand.py opp1.py opp2.py
```

## Attribution

The base agent is the community "Shepherd's Ledger" tape-replay chassis; the ~25k-line
chassis inside each file under `agents/` is not our work. Our contribution is the layer
stack in `layers/`, the evaluation methodology in `harness/` and `analysis/`, and the
research in `FINDINGS.md`.
