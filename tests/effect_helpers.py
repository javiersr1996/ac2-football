"""Synthetic worlds for the estimator of task 20: planted units, and planted tracking.

Two levels. :func:`planted_units` writes :class:`~ac2fb.defence.effect.EffectUnit`\\ s directly
(a planted effect, a planted pre-trend): the claim lives in the statistic. The tracking worlds
(:func:`tracking_match`, :func:`through_the_pipeline`) write positions of the carrier, two
rivals and the ball, and the units come out of the real pipeline
(``pressure.score_receptions``, ``design.design_units``, ``effect.effect_units``): the claim
lives in the cause, the strata or the instant. Every number a test expects is planted here.

Geometry: the carrier (team 1, attacking +x) stands at the origin of the middle third; rivals
(team 2) stand on the +x axis, straight between the carrier and the goal, so a rival at ``d``
metres weighs ``1 - d / 10``. A unit is pressed (index at least 0.5) with one rival within 5 m.
Receptions are 40 frames apart (more than W, so none is excluded by the window overlap).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from layer2_helpers import Row, frames_table, make_match

from ac2fb.defence import design, effect, power, probe_s1
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.defence.pressure import Reception
from ac2fb.reliability.long import long_table

SPACING = 40  # frames between receptions
FIRST = 100
LATE = 10  # the mutation reads the cause this many frames after t (one second)
Pos = tuple[float, float]


# --- planted units -----------------------------------------------------------------------------


def planted_units(
    seed: int,
    *,
    tau: float = 0.0,
    persistence: float = 0.0,
    shift: float = 0.0,
    matches: int = 10,
    strata: int = 3,
    n: int = 90,
    share: float = 0.4,
) -> list[effect.EffectUnit]:
    """Units with ``y = level + persistence * x + tau * G + e`` and ``x = e' + shift * G``.

    ``tau`` is in sd of the noise ``e`` (unit variance), ``shift`` the pressed units' extra
    forward ball before ``t`` (the pre-trend), ``persistence`` how much of it the outcome keeps.
    Each cell has its own level of ``y`` and of ``x``, so that a pooled comparison would be off.
    """
    rng = np.random.default_rng([20, seed])
    units: list[effect.EffectUnit] = []
    frame = FIRST
    for m in range(matches):
        for s in range(strata):
            g = rng.random(n) < share
            x = rng.normal(0.0, 1.0, n) + shift * g + 2.0 * s
            y = 3.0 * s + persistence * x + tau * g + rng.normal(0.0, 1.0, n)
            for k in range(n):
                units.append(
                    effect.EffectUnit(
                        match=m + 1,
                        period=1,
                        frame=frame,
                        stratum=f"s{s}",
                        pressed=bool(g[k]),
                        possession=f"p{k // 2}",
                        pre=float(x[k]),
                        outcome=float(y[k]),
                        extrapolated_players=0,
                        ball_detected=True,
                    )
                )
                frame += SPACING
    return units


def plain_difference(units: Sequence[effect.EffectUnit]) -> float:
    """The unadjusted statistic: the weighted mean over cells of (difference of means) / sd."""
    cells: dict[tuple[int, str], list[effect.EffectUnit]] = {}
    for u in units:
        cells.setdefault((u.match, u.stratum), []).append(u)
    num = den = 0.0
    for us in cells.values():
        y = np.array([u.outcome for u in us], dtype=float)
        g = np.array([u.pressed for u in us])
        if g.sum() < 5 or (~g).sum() < 5:
            continue
        w = g.sum() * (~g).sum() / len(us)
        num += w * (y[g].mean() - y[~g].mean()) / y.std(ddof=1)
        den += w
    return num / den


# --- planted tracking --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rival:
    """A rival at ``t``: placed at ``pos`` and detected, or interpolated in a detection gap.

    ``gap`` gives the two detections (``t - 7`` and ``t + 7``) between which the provider lists
    the rival on the straight line, not detected, so that its position at ``t`` is the midpoint.
    """

    pos: Pos | None = None
    detected: bool = True
    gap: tuple[Pos, Pos] | None = None
    late: Pos | None = None  # where the rival stands LATE frames after t (detected)


@dataclass(frozen=True)
class Spec:
    """One reception: the ball arriving (``in_adv``), leaving (``out_adv``) and the rivals."""

    in_adv: float
    out_adv: float
    rivals: tuple[Rival, Rival]
    carrier_detected: bool = True
    ball_end_detected: bool = True
    jitter: Sequence[float] = field(default=(0.0, 0.0, 0.0, 0.0))


def ahead(d: float) -> Pos:
    return (d, 0.0)


FAR = Rival(pos=(-30.0, 0.0))  # well outside the radius, behind


def tracking_match(match_id: int, specs: Sequence[Spec]) -> power.C1Inputs:
    """One match of the specs, one reception each, in the shape the design reads."""
    series: dict[int, list[Row]] = {1: [], 11: [], 12: []}
    ball: list[Row] = []
    receptions: list[Reception] = []
    late = any(r.late is not None for sp in specs for r in sp.rivals)
    for k, sp in enumerate(specs):
        t = FIRST + SPACING * k
        series[1].append((t, 0.0, 0.0, sp.carrier_detected))
        if late:
            series[1].append((t + LATE, 0.0, 0.0, True))
        for player, rival in zip((11, 12), sp.rivals, strict=True):
            series[player] += _rival_rows(t, rival, sp.jitter)
            if rival.late is not None:
                series[player].append((t + LATE, rival.late[0], rival.late[1], True))
        ball += [(t - W, -sp.in_adv, 0.5, True)]
        if late:
            ball += [(t - 3, -sp.in_adv * 3 / W, 0.5, True)]
        ball += [(t, 0.0, 0.5, True)]
        if late:
            ball += [(t + LATE, sp.out_adv * LATE / W, 0.5, True)]
        ball += [(t + W, sp.out_adv, 0.5, sp.ball_end_detected)]
        receptions.append(Reception(f"e{k}", 1, t, 1, 1, k % 5 + 1))
    teams = {1: 1, 11: 2, 12: 2}
    match = make_match(series, teams, ball=ball, signs={1: 1, 2: -1})
    match = dataclasses.replace(match, match_id=match_id)
    s1 = probe_s1.MatchInputs(
        match, long_table(frames_table(series, teams, ball)), tuple(receptions), len(receptions)
    )
    possessions = {f"e{k}": f"p{k // 2}" for k in range(len(specs))}
    return power.C1Inputs(s1, possessions)


def _rival_rows(t: int, rival: Rival, jitter: Sequence[float]) -> list[Row]:
    if rival.gap is None:
        assert rival.pos is not None
        return [(t, rival.pos[0], rival.pos[1], rival.detected)]
    (x1, y1), (x2, y2) = rival.gap
    # Detected frames with a kink on both sides (so detected stretches do have a residual),
    # then the straight line between the two detections, listed as not detected.
    rows: list[Row] = [
        (t - 9, x1 + jitter[0], y1 - jitter[0], True),
        (t - 8, x1 - jitter[1], y1 + jitter[1], True),
        (t - 7, x1, y1, True),
    ]
    for f in range(t - 6, t + 7):
        a = (f - (t - 7)) / 14
        rows.append((f, x1 + a * (x2 - x1), y1 + a * (y2 - y1), False))
    rows += [
        (t + 7, x2, y2, True),
        (t + 8, x2 + jitter[2], y2 - jitter[2], True),
        (t + 9, x2 - jitter[3], y2 + jitter[3], True),
    ]
    return rows


def through_the_pipeline(
    worlds: dict[int, power.C1Inputs],
) -> list[effect.EffectUnit]:
    """The kept units with their outcome, for each match, by the real design and reader."""
    out: list[effect.EffectUnit] = []
    for inputs in worlds.values():
        out += effect.effect_units(design.design_units(inputs), inputs.s1.match)
    return out


def moved(inputs: power.C1Inputs, period: int, team: int) -> power.C1Inputs:
    """The same world, the carrier's team (1, attacking +x in period 1) in ``period`` as ``team``.

    Period 2 turns both teams round; team 2 swaps the two labels. Every x of the players and
    the ball is flipped when the carrier's team then attacks -x, so it sees the same pitch.
    The signs of period 1 stay listed: a reader that takes another period's sign or another
    team's reads a wrong sign, not a missing one.
    """
    m = inputs.s1.match
    signs = {(period, k): s if period == 1 else -s for (_, k), s in m.attack_sign.items()}
    flip = signs[(period, team)]
    match = dataclasses.replace(
        m,
        team=m.team if team == 1 else 3 - m.team,
        period=np.full_like(m.period, period),
        x=flip * m.x,
        ball_x=flip * m.ball_x,
        ball_period=np.full_like(m.ball_period, period),
        attack_sign={**m.attack_sign, **signs},
    )
    receptions = tuple(
        dataclasses.replace(r, period=period, team=team) for r in inputs.s1.receptions
    )
    s1 = dataclasses.replace(inputs.s1, match=match, receptions=receptions)
    return dataclasses.replace(inputs, s1=s1)


# --- the planted worlds ------------------------------------------------------------------------

# Incoming ball by stratum: (low, high) metres along the attack, mean outgoing advance (the ball
# keeps going when it came forward: a step in the incoming advance, no line removes it), the
# chance of pressure (it comes with a forward ball), and how common the stratum is.
NOISE = 1.0  # sd of the outgoing advance inside a stratum
CONFOUNDED = (
    ((-16.0, -10.5), 0.0, 0.15, 0.15),
    ((-9.0, -2.5), 0.0, 0.25, 0.20),
    ((-1.5, 1.5), 0.0, 0.40, 0.25),
    ((2.5, 9.0), 12.0, 0.70, 0.25),
    ((10.5, 16.0), 12.0, 0.85, 0.15),
)


def confounded_world(seed: int, matches: int = 10, n: int = 400) -> dict[int, power.C1Inputs]:
    """Pressure comes with a forward incoming ball and the outgoing ball follows the incoming one.

    No causal effect of pressure: the outgoing advance is the stratum's mean plus noise.
    """
    worlds: dict[int, power.C1Inputs] = {}
    shares = [s[3] for s in CONFOUNDED]
    for m in range(1, matches + 1):
        rng = np.random.default_rng([22, seed, m])
        specs: list[Spec] = []
        for _ in range(n):
            (lo, hi), mean, chance, _ = CONFOUNDED[int(rng.choice(len(CONFOUNDED), p=shares))]
            pressed = rng.random() < chance
            d = rng.uniform(2.0, 4.0) if pressed else rng.uniform(7.5, 9.5)
            specs.append(
                Spec(
                    in_adv=float(rng.uniform(lo, hi)),
                    out_adv=float(mean + rng.normal(0.0, NOISE)),
                    rivals=(Rival(pos=ahead(float(d))), FAR),
                )
            )
        worlds[m] = tracking_match(m, specs)
    return worlds


def collapse_strata(units: Sequence[effect.EffectUnit]) -> list[effect.EffectUnit]:
    """The mutation 'no strata': every unit of a match in one stratum."""
    return [dataclasses.replace(u, stratum="all") for u in units]


def extrapolated_world(seed: int, matches: int = 10, n: int = 200) -> dict[int, power.C1Inputs]:
    """The outcome is driven by the TRUE pressure; the listed rivals may be interpolated.

    Half the units are truly pressed: one of the two rivals (at random) stands 2 to 4 m ahead,
    the other 8 to 9.5 m. A rival in a detection gap is listed on the straight line between two
    detections 7 frames either side; their midpoint, where it is listed at ``t``, is drawn
    without looking at the truth (2 to 4 m ahead with chance 0.25, else 8 to 9.5 m).
    The count of interpolated rivals is 0, 1 or 2 with chances 0.4, 0.3, 0.3. Outgoing
    advance: ``-3`` metres when truly pressed, noise sd 2, a single lateral stratum.
    """
    worlds: dict[int, power.C1Inputs] = {}
    for m in range(1, matches + 1):
        rng = np.random.default_rng([23, seed, m])
        specs: list[Spec] = []
        for _ in range(n):
            truly = rng.random() < 0.5
            presser = int(rng.integers(0, 2))
            true_d = [float(rng.uniform(8.0, 9.5)), float(rng.uniform(8.0, 9.5))]
            if truly:
                true_d[presser] = float(rng.uniform(2.0, 4.0))
            count = int(rng.choice(3, p=[0.4, 0.3, 0.3]))
            gapped = {0: [], 1: [int(rng.integers(0, 2))], 2: [0, 1]}[count]
            rivals: list[Rival] = []
            for i in range(2):
                if i in gapped:
                    mid = float(
                        rng.uniform(2.0, 4.0) if rng.random() < 0.25 else rng.uniform(8.0, 9.5)
                    )
                    delta = float(rng.uniform(0.5, 1.5))
                    rivals.append(
                        Rival(gap=(ahead(mid + delta), ahead(mid - delta)), detected=False)
                    )
                else:
                    rivals.append(Rival(pos=ahead(true_d[i])))
            specs.append(
                Spec(
                    in_adv=float(rng.uniform(-1.5, 1.5)),
                    out_adv=float(-3.0 * truly + rng.normal(0.0, 2.0)),
                    rivals=(rivals[0], rivals[1]),
                    jitter=tuple(float(v) for v in rng.uniform(0.2, 0.6, 4)),
                )
            )
        worlds[m] = tracking_match(m, specs)
    return worlds


def reverse_world(seed: int, matches: int = 10, n: int = 200) -> dict[int, power.C1Inputs]:
    """Reverse causation: the defenders close in AFTER the ball failed to advance.

    The outgoing advance is noise (sd 3) and the ball 'failed' when it is negative. At ``t`` a
    rival stands 3 m ahead (pressed) with chance 0.4 or 9 m ahead, whatever the ball does next;
    ``LATE`` frames later it stands 3 m ahead exactly when the ball failed. The incoming ball
    is lateral noise, so nothing before ``t`` tells the two readings apart.
    """
    worlds: dict[int, power.C1Inputs] = {}
    for m in range(1, matches + 1):
        rng = np.random.default_rng([24, seed, m])
        specs: list[Spec] = []
        for _ in range(n):
            out = float(rng.normal(0.0, 3.0))
            near_now = rng.random() < 0.4
            now = ahead(3.0 if near_now else 9.0)
            soon = ahead(3.0 if out < 0 else 9.0)
            specs.append(
                Spec(
                    in_adv=float(rng.uniform(-1.5, 1.5)),
                    out_adv=out,
                    rivals=(Rival(pos=now, late=soon), FAR),
                )
            )
        worlds[m] = tracking_match(m, specs)
    return worlds


def cause_read_late(worlds: dict[int, power.C1Inputs]) -> list[effect.EffectUnit]:
    """The mutation 'cause at t + 1 s': the pressed flag from the index LATE frames after ``t``.

    Everything else (stratum, pre-trend, outcome) stays at ``t``.
    """
    out: list[effect.EffectUnit] = []
    for inputs in worlds.values():
        at_t = design.design_units(inputs)
        moved = tuple(dataclasses.replace(r, frame=r.frame + LATE) for r in inputs.s1.receptions)
        late = design.design_units(
            power.C1Inputs(dataclasses.replace(inputs.s1, receptions=moved), inputs.possessions)
        )
        flag = {u.event_id: u.pressed for u in late}
        mixed = [dataclasses.replace(u, pressed=flag[u.event_id]) for u in at_t]
        out += effect.effect_units(mixed, inputs.s1.match)
    return out
