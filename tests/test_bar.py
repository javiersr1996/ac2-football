"""The calibration bar, its null and its simulated power, on hand-made designs.

Every expected number is built here from the planted design, never from the code under test.

Mutations, each annotated with the test that kills it:

* the approximation with the wrong null variance (the unblocked ``1 / sum w`` without the root,
  or the blocked one with the unblocked variance), or a one-sided ``q``:
  ``test_the_approximation_matches_the_full_permutation``;
* noise that ignores the within-possession correlation (``rho`` taken as 0), or that draws the
  shared part once per unit instead of once per possession:
  ``test_ignoring_the_possession_correlation_inflates_the_power`` and
  ``test_the_noise_carries_the_planted_correlation``;
* a sign rule of 7 of 10: ``test_the_sign_condition_needs_eight_matches``;
* a match without a cell counted as agreeing: ``test_a_match_without_a_cell_never_agrees``;
* cells below the minimum kept: ``test_cells_below_the_minimum_are_left_out``;
* a correlation that does not standardise inside each stratum, or counts a unit with itself:
  ``test_the_correlation_recovers_a_planted_rho``;
* a count bound of 2 of 2000: ``test_the_bar_allows_one_extreme_draw_of_two_thousand``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ac2fb.defence import bar

MATCHES = 10


def toy(
    seed: int,
    *,
    strata: int = 2,
    per: int = 24,
    possession: int = 3,
    clustered: bool = False,
    matches: int = MATCHES,
) -> bar.Design:
    """``per`` units per stratum and match, ``possession`` consecutive units per possession.

    With ``clustered`` the whole possession shares its group (alternating), else each unit's
    group is a coin.
    """
    rng = np.random.default_rng(seed)
    match, stratum, group, owner = [], [], [], []
    for m in range(matches):
        for s in range(strata):
            for k in range(per):
                match.append(m)
                stratum.append(f"s{s}")
                group.append((k // possession) % 2 == 0 if clustered else bool(rng.random() < 0.5))
                owner.append(f"{s}:{k // possession}")
    return bar.Design(
        tuple(range(matches)), np.array(match), tuple(stratum), np.array(group), tuple(owner)
    )


def test_the_bar_allows_one_extreme_draw_of_two_thousand() -> None:
    # p = (1 + count) / 2001: a count of 1 gives 0.0009995, a count of 2 gives 0.0014993.
    assert bar.N_PERMUTATIONS == 2000 and bar.BAR_P == 0.00135
    assert (1 + 1) / 2001 <= 0.00135 < (1 + 2) / 2001
    assert bar.BAR_COUNT_AT_MOST == 1


def test_the_pass_probability_is_the_binomial_tail() -> None:
    # By hand: P(Binomial(2000, q) <= 1) = (1 - q)^2000 + 2000 q (1 - q)^1999.
    for z in (0.0, 2.0, 3.0, 3.2, 3.5, 4.0, 6.0):
        q = math.erfc(z / math.sqrt(2.0))
        expected = (1 - q) ** 2000 + 2000 * q * (1 - q) ** 1999
        got = float(bar.pass_probability(np.array([z]))[0])
        assert got == pytest.approx(expected, rel=1e-9, abs=1e-300)
    assert float(bar.pass_probability(np.array([-4.0]))[0]) == pytest.approx(
        float(bar.pass_probability(np.array([4.0]))[0])
    )


@pytest.mark.parametrize("blocked", [False, True])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_approximation_matches_the_full_permutation(blocked: bool, seed: int) -> None:
    # The same simulated data sets, the bar applied twice: with the normal approximation of the
    # null and with N_PERMUTATIONS real null draws. Blocked: groups shared by a possession and a
    # within-possession correlation of 0.3, where the block matters.
    design = toy(seed, clustered=blocked)
    prepared = bar.prepare(design)
    rho = 0.3 if blocked else 0.0
    noise = bar.draw_noise(prepared, [rho] * MATCHES, 3000, np.random.default_rng([seed, 9]))
    draws = bar.null_draws(prepared, blocked, np.random.default_rng([seed, 7]))
    rates = []
    for effect in (0.0, 0.3, 0.45, 0.6):
        approx = float(bar.bar_probability(prepared, noise, effect, blocked).mean())
        full = float(bar.full_passes(prepared, noise, effect, blocked, draws).mean())
        assert abs(approx - full) < 0.025, (effect, approx, full)
        rates.append(full)
    assert rates[0] < 0.01 and 0.15 < rates[1] < 0.6 and rates[3] > 0.9  # the set is not trivial


def test_the_full_null_draws_stay_inside_cells_and_possessions() -> None:
    design = toy(4)
    prepared = bar.prepare(design)
    labels = bar.null_draws(prepared, False, np.random.default_rng(1), draws=50)
    cell = prepared.by_cell_cell
    for row in np.asarray(labels, dtype=bool):
        assert np.array_equal(
            np.bincount(cell[row], minlength=len(prepared.weight)), prepared.cell_n1
        )
    signs = np.asarray(bar.null_draws(prepared, True, np.random.default_rng(1), draws=50))
    assert signs.shape == (50, len(prepared.cluster_match))
    assert set(np.unique(signs).tolist()) == {-1.0, 1.0}


def test_ignoring_the_possession_correlation_inflates_the_power() -> None:
    # Groups shared by a possession: a correlated noise moves whole possessions, so the pooled
    # effect varies more and, near 80 %, the bar passes less often than with independent units.
    # Blocked (the protocol's null above BLOCK_RHO) the loss is large; unblocked, smaller,
    # because the unblocked null also fires more often without an effect.
    design = toy(5, clustered=True)
    for blocked, effect, margin in ((True, 0.4, 0.25), (False, 0.5, 0.04)):
        with_rho = bar.pass_rates(design, [0.4] * MATCHES, blocked, [effect], (5, 1), 1000)
        without = bar.pass_rates(design, [0.0] * MATCHES, blocked, [effect], (5, 1), 1000)
        assert with_rho[0] < without[0] - margin, (blocked, with_rho, without)


def test_the_noise_carries_the_planted_correlation() -> None:
    design = toy(6, possession=4)
    prepared = bar.prepare(design)
    noise = bar.draw_noise(prepared, [0.3] * MATCHES, 4000, np.random.default_rng(3))
    assert float(noise.var()) == pytest.approx(1.0, abs=0.02)
    same = [
        float(np.mean(noise[:, a] * noise[:, b]))
        for a in range(40)
        for b in range(40)
        if a < b and prepared.unit_cluster[a] == prepared.unit_cluster[b]
    ]
    other = [
        float(np.mean(noise[:, a] * noise[:, b]))
        for a in range(40)
        for b in range(40)
        if a < b and prepared.unit_cluster[a] != prepared.unit_cluster[b]
    ]
    assert len(same) > 10 and len(other) > 10
    assert float(np.mean(same)) == pytest.approx(0.3, abs=0.04)
    assert float(np.mean(other)) == pytest.approx(0.0, abs=0.04)


def _reversed(design: bar.Design, flipped: set[int], effect: float, seed: int) -> np.ndarray:
    """Noise that turns the planted effect into its opposite in the ``flipped`` matches."""
    prepared = bar.prepare(design)
    base = bar.draw_noise(prepared, [0.0] * MATCHES, 200, np.random.default_rng(seed))
    turn = np.isin(prepared.unit_match, sorted(flipped)) & prepared.unit_group
    shifted: np.ndarray = base - 2.0 * effect * turn
    return shifted


def test_the_sign_condition_needs_eight_matches() -> None:
    design = toy(7, per=40)
    prepared = bar.prepare(design)
    two = _reversed(design, {0, 1}, 1.5, 1)
    three = _reversed(design, {0, 1, 2}, 1.5, 1)
    assert float(bar.bar_probability(prepared, two, 1.5, False).mean()) > 0.99
    assert float(bar.bar_probability(prepared, three, 1.5, False).mean()) == 0.0


def test_a_match_without_a_cell_never_agrees() -> None:
    # Three matches hold 4 pressed units per stratum (below MIN_CELL): only 7 can agree.
    full = toy(8, per=40)
    keep = [
        i
        for i in range(len(full.match))
        if not (full.match[i] < 3 and full.pressed[i] and int(full.possession[i].split(":")[1]) > 1)
    ]
    design = bar.Design(
        full.matches,
        full.match[keep],
        tuple(full.stratum[i] for i in keep),
        full.pressed[keep],
        tuple(full.possession[i] for i in keep),
    )
    prepared = bar.prepare(design)
    assert set(prepared.cell_match.tolist()) == set(range(3, MATCHES))
    noise = bar.draw_noise(prepared, [0.0] * MATCHES, 200, np.random.default_rng(2))
    assert float(bar.bar_probability(prepared, noise, 2.0, False).mean()) == 0.0


def test_cells_below_the_minimum_are_left_out() -> None:
    def design(pressed: int, free: int) -> bar.Design:
        groups = [True] * pressed + [False] * free
        n = len(groups)
        return bar.Design(
            (1,),
            np.zeros(n, dtype=np.int64),
            ("a",) * n,
            np.array(groups),
            tuple(map(str, range(n))),
        )

    assert len(bar.prepare(design(5, 5)).weight) == 1
    assert len(bar.prepare(design(5, 4)).weight) == 0
    assert len(bar.prepare(design(4, 9)).weight) == 0
    assert bar.prepare(design(5, 5)).weight[0] == pytest.approx(2.5)  # 5 * 5 / 10


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_the_correlation_recovers_a_planted_rho(seed: int) -> None:
    # Possessions of 4 units over three strata with very different means and sds: only the
    # standardisation inside each stratum leaves the planted 0.25.
    rng = np.random.default_rng(seed)
    values, strata, owners = [], [], []
    shift = {"a": (0.0, 1.0), "b": (40.0, 5.0), "c": (-25.0, 0.2)}
    for k in range(1500):
        shared = rng.standard_normal() * math.sqrt(0.25)
        for j in range(4):
            name = "abc"[(k + j) % 3]
            mean, sd = shift[name]
            values.append(mean + sd * (shared + rng.standard_normal() * math.sqrt(0.75)))
            strata.append(name)
            owners.append(f"p{k}")
    got = bar.within_possession_correlation(values, strata, owners)
    assert got.rho == pytest.approx(0.25, abs=0.04)
    assert got.pairs == 1500 * 6 and got.possessions == 1500 and got.units == 6000
    alone = bar.within_possession_correlation(values, strata, [f"u{i}" for i in range(6000)])
    assert alone.rho is None and alone.pairs == 0


def test_mde80_is_the_first_effect_that_reaches_the_target() -> None:
    design = toy(9, per=30)
    power = bar.mde80(design, [0.0] * MATCHES, False, (9,), replicates=400)
    assert power.mde80 is not None
    rates = dict(zip(power.effects, power.pass_rate, strict=True))
    assert rates[power.mde80] >= bar.POWER_TARGET
    below = [e for e in power.effects if e < power.mde80]
    assert below and all(rates[e] < bar.POWER_TARGET for e in below)
    assert any(round(e * 100) % 5 for e in power.effects)  # refined inside the coarse step
    few = toy(9, per=30, matches=7)  # seven matches can never give eight signs
    assert bar.mde80(few, [0.0] * 7, False, (9,), replicates=100).mde80 is None


def test_the_power_is_reproducible_with_its_seed() -> None:
    design = toy(10)
    a = bar.pass_rates(design, [0.1] * MATCHES, True, [0.2, 0.4], (1, 2), 300)
    b = bar.pass_rates(design, [0.1] * MATCHES, True, [0.2, 0.4], (1, 2), 300)
    c = bar.pass_rates(design, [0.1] * MATCHES, True, [0.2, 0.4], (1, 3), 300)
    assert a == b and a != c
