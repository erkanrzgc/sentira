"""Surge episodes on strict as-of synthetic series; no collection or network access.

The hand-chosen thresholds in tests/fixtures/hand-measured.toml supply c_min = 6,
k_floor = 10 and H = 72 h with the shipped registration.
With no background rows the baseline is zero, so c_min and k_floor bind and every
expected tick below can be checked by hand.
"""

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
START = datetime(2030, 1, 1, tzinfo=UTC)
# The 28-day baseline window first lies wholly inside the data on this day.
DAY = START + timedelta(days=28)
HOUR = timedelta(hours=1)
H = timedelta(hours=72)


@pytest.fixture(scope="module")
def locked(hand_locked):
    return hand_locked


def rows(first, hours, per_hour, *, visible_at=None):
    from sentira.series.episodes import Observation

    published = [
        first + timedelta(hours=h, minutes=30) for h in range(hours) for _ in range(per_hour)
    ]
    return [Observation(p, visible_at or p) for p in published]


def detect(locked, observations, *, end, cell=None):
    from sentira.series.episodes import detect_episodes

    return detect_episodes(observations, locked, cell or locked.primary_cell, start=START, end=end)


def test_tk_is_first_tick_at_which_asof_series_reaches_k(locked):
    # Two rows per hour from 00:30. The trailing count reaches c_min = 6 at 03:00;
    # rows published from 03:00 reach k = 10 when the 07:30 pair is visible.
    live = rows(DAY, 12, 2)
    (episode,) = detect(locked, live, end=DAY + timedelta(days=10))
    assert episode.onset_at == DAY + 3 * HOUR
    assert episode.baseline == 0 and episode.k == 10 and episode.k_floor_binds
    assert episode.tau_k == DAY + 8 * HOUR
    assert episode.overshoot == 1.0

    # Delayed visibility moves tau_k to the tick at which the rows are visible.
    delayed = rows(DAY, 3, 2) + rows(DAY + 3 * HOUR, 5, 2, visible_at=DAY + 9 * HOUR)
    delayed += rows(DAY + 8 * HOUR, 4, 2)
    (late,) = detect(locked, delayed, end=DAY + timedelta(days=10))
    assert late.onset_at == DAY + 3 * HOUR
    assert late.tau_k == DAY + 9 * HOUR
    assert late.overshoot == 1.2


def test_onset_invariant_to_rows_invisible_at_T(locked):
    from sentira.series.episodes import Observation

    generator = random.Random(7)
    observations = []
    for hour in range(40 * 24):
        burst = 6 if 29 * 24 + 5 <= hour < 29 * 24 + 20 or 33 * 24 <= hour < 33 * 24 + 9 else 0
        for _ in range(generator.randint(0, 2) + burst):
            published = START + timedelta(hours=hour, minutes=generator.randint(0, 59))
            delay = timedelta(minutes=generator.choice((0, 0, 0, 20, 90, 600, 1800)))
            observations.append(Observation(published, published + delay))
    T = DAY + timedelta(days=7)
    known = {}
    for cell in (locked.primary_cell, locked.grid[0], locked.grid[-1]):
        baseline = known[cell] = detect(locked, observations, end=T, cell=cell)
        visible = [o for o in observations if o.visible_at <= T]
        hidden = [o for o in observations if o.visible_at > T]
        mutated = visible + [
            Observation(o.published_at, o.visible_at + timedelta(days=3)) for o in hidden[::2]
        ]
        mutated += [Observation(T - timedelta(hours=h), T + HOUR) for h in range(1, 200)]
        assert detect(locked, mutated, end=T, cell=cell) == baseline
    assert any(episode.tau_k for episode in known[locked.primary_cell])


def test_detected_at_crossing_excluded_from_t1_population(locked):
    # Onset at 03:00; twenty rows published after onset arrive together at 13:00,
    # so the episode is first known at size 20 = 2k.
    observations = rows(DAY, 3, 2) + rows(DAY + 3 * HOUR, 10, 2, visible_at=DAY + 13 * HOUR)
    (episode,) = detect(locked, observations, end=DAY + timedelta(days=10))
    assert episode.tau_k == DAY + 13 * HOUR
    assert episode.overshoot == 2.0
    assert episode.detected_at_crossing
    # No crossing after tau_k is invented; the outcome was already known at tau_k.
    assert episode.label == "detected_at_crossing"
    assert episode.crossed_2k_at == episode.tau_k == episode.resolves_at
    assert not episode.in_t1_population


def test_unresolved_horizon_is_censored_not_negative(locked):
    observations = rows(DAY, 12, 2)
    tau_k = DAY + 8 * HOUR
    (short,) = detect(locked, observations, end=tau_k + H - HOUR)
    assert short.label == "censored" and not short.in_t1_population
    (full,) = detect(locked, observations, end=tau_k + H)
    assert full.label == "negative" and full.in_t1_population


def test_resolution_time_is_tk_plus_H_for_both_classes(locked):
    tau_k = DAY + 8 * HOUR
    # Twelve hours of rows stop at size 18 < 2k; twenty hours reach 2k at 13:00.
    (negative,) = detect(locked, rows(DAY, 12, 2), end=DAY + timedelta(days=10))
    (positive,) = detect(locked, rows(DAY, 20, 2), end=DAY + timedelta(days=10))
    assert negative.label == "negative" and positive.label == "positive"
    assert positive.crossed_2k_at == DAY + 13 * HOUR
    assert negative.resolves_at == positive.resolves_at == tau_k + H
    # An observed crossing does not resolve the label before tau_k + H.
    (early,) = detect(locked, rows(DAY, 20, 2), end=tau_k + H - HOUR)
    assert early.label == "censored"


def test_level_shift_does_not_extend_episode_past_max_duration(locked):
    # One row per hour, then two per hour from day 28 onward. The rolling baseline
    # never exceeds the new level, so only the maximum duration (2H) ends it.
    observations = rows(START, 28 * 24, 1) + rows(DAY, 12 * 24, 2)
    episodes = detect(locked, observations, end=START + timedelta(days=40))
    first = episodes[0]
    assert first.onset_at == DAY + timedelta(days=1)
    assert first.baseline == 24 and first.k == 24 and not first.k_floor_binds
    assert first.end_reason == "max_duration"
    assert first.ended_at - first.onset_at == 2 * H
    assert first.label == "positive"


def test_episode_ends_after_quiet_period_below_current_baseline(locked):
    # A burst over one row per hour, then a day with no rows: the trailing count
    # stays below the current baseline for 24 hours and the episode ends.
    observations = rows(START, 29 * 24, 1) + rows(DAY + timedelta(days=1), 24, 4)
    observations += rows(DAY + timedelta(days=3), 10 * 24, 1)
    episodes = detect(locked, observations, end=START + timedelta(days=42))
    first = episodes[0]
    assert first.end_reason == "quiet"
    assert first.ended_at < first.onset_at + 2 * H


def test_end_rule_uses_current_not_frozen_baseline(locked):
    from sentira.backtest.registration import Cell

    # Fourteen days at 24 and fourteen at 96 freeze b* = 60 at onset. One day
    # later the rolling median is 96, so 72 a day is below the current baseline
    # although it is above the frozen one.
    observations = rows(START, 14 * 24, 1) + rows(START + timedelta(days=14), 15 * 24, 4)
    observations += rows(DAY + timedelta(days=1), 10 * 24, 3)
    episodes = detect(locked, observations, end=START + timedelta(days=40), cell=Cell(1.5, 1.0, 72))
    first = episodes[0]
    assert first.onset_at == DAY and first.baseline == 60
    assert first.end_reason == "quiet"
    assert first.ended_at == DAY + timedelta(days=2)


def test_no_onset_during_refractory_period(locked):
    from sentira.backtest.registration import Cell

    # The first episode ends quietly at day 30; a burst twelve hours later would
    # open an episode, but it falls inside the 72-hour refractory period.
    observations = rows(START, 14 * 24, 1) + rows(START + timedelta(days=14), 15 * 24, 4)
    observations += rows(DAY + timedelta(days=1), 10 * 24, 3)
    observations += rows(DAY + timedelta(days=2, hours=12), 6, 20)
    episodes = detect(locked, observations, end=START + timedelta(days=40), cell=Cell(1.5, 1.0, 72))
    first = episodes[0]
    assert first.ended_at == DAY + timedelta(days=2)
    assert all(e.onset_at >= first.ended_at + timedelta(hours=72) for e in episodes[1:])


def test_baseline_includes_late_rows_for_past_days(locked):
    # Fourteen days at 24 and thirteen at 96; the 96 rows of the last baseline day
    # arrive at noon on day 29. Once visible they raise the median from 24 to 60,
    # so the noon trailing count of 84 no longer reaches 2 x baseline.
    observations = rows(START, 14 * 24, 1) + rows(START + timedelta(days=14), 13 * 24, 4)
    observations += rows(DAY - timedelta(days=1), 24, 4, visible_at=DAY + 12 * HOUR)
    observations += rows(DAY, 24, 3)
    assert detect(locked, observations, end=DAY + timedelta(days=3)) == ()


def test_open_episode_below_k_is_unresolved(locked):
    # Onset at 03:00; the data end two hours later, before the episode can reach k.
    (episode,) = detect(locked, rows(DAY, 3, 2), end=DAY + 5 * HOUR)
    assert episode.tau_k is None and episode.end_reason == "open"
    assert episode.label == "open"
    (ended,) = detect(locked, rows(DAY, 3, 2), end=DAY + timedelta(days=10))
    assert ended.label == "below_k" and ended.end_reason == "max_duration"


def test_trailing_window_scales_daily_baseline(locked, tmp_path):
    from sentira.backtest.registration import load_locked, write_lock

    examples = ROOT / "examples"
    registration = tmp_path / "registration.toml"
    registration.write_text(
        (examples / "synthetic-registration.toml")
        .read_text(encoding="utf-8")
        .replace("trailing_hours = 24", "trailing_hours = 12"),
        encoding="utf-8",
    )
    lock = tmp_path / "registration.lock"
    measured = ROOT / "tests/fixtures/hand-measured.toml"
    write_lock(registration, measured, lock)
    twelve = load_locked(registration, measured, lock)
    # b = 24 a day, so a 12-hour window expects 12 rows and m = 2 needs 24. At
    # three rows an hour the 12-hour count is 12 + 2h, reaching 24 at 06:00.
    observations = rows(START, 28 * 24, 1) + rows(DAY, 48, 3)
    episodes = detect(twelve, observations, end=DAY + timedelta(days=5))
    assert episodes[0].onset_at == DAY + 6 * HOUR
    assert episodes[0].baseline == 24


def test_grid_pass_matches_single_cell_detection(locked):
    from sentira.series.episodes import Observation, detect_episodes, detect_grid

    generator = random.Random(23)
    observations = []
    for hour in range(45 * 24):
        burst = 5 if hour % (6 * 24) in range(10, 22) else 0
        for _ in range(generator.randint(0, 2) + burst):
            published = START + timedelta(hours=hour, minutes=generator.randint(0, 59))
            delay = timedelta(minutes=generator.choice((0, 0, 30, 240)))
            observations.append(Observation(published, published + delay))
    end = START + timedelta(days=45)
    together = detect_grid(observations, locked, locked.grid, start=START, end=end)
    assert set(together) == set(locked.grid)
    for cell in locked.grid:
        alone = detect_episodes(observations, locked, cell, start=START, end=end)
        assert together[cell] == alone
    assert sum(len(found) for found in together.values()) > 36


def test_detection_requires_locked_registration_grid_cell_and_hour_bounds(locked):
    from sentira.backtest.registration import Cell
    from sentira.series.episodes import Observation, detect_episodes

    observations = rows(DAY, 2, 1)
    end = DAY + timedelta(days=2)
    with pytest.raises(ValueError, match="locked"):
        detect_episodes(
            observations, locked.registration, locked.primary_cell, start=START, end=end
        )
    with pytest.raises(ValueError, match="grid"):
        detect_episodes(observations, locked, Cell(2.5, 1.0, 72), start=START, end=end)
    with pytest.raises(ValueError, match="whole hours"):
        detect_episodes(
            observations, locked, locked.primary_cell, start=START + timedelta(minutes=5), end=end
        )
    with pytest.raises(ValueError):
        detect_episodes(observations, locked, locked.primary_cell, start=end, end=START)
    with pytest.raises(ValueError, match="visible before"):
        Observation(DAY, DAY - HOUR)
    with pytest.raises(ValueError):
        detect_episodes([object()], locked, locked.primary_cell, start=START, end=end)
