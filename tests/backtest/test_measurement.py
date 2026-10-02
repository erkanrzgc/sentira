"""The measured addendum computed by registered label-free rules; synthetic only.

The shipped registration sets D0 = 2030-01-01 and O1 = 2030-04-29 (118 days),
trailing window 24 h, c_min_z 3, k_floor_z 2, both minimums 5, at least three
half-life episodes and a horizon multiple of 3 over the grid {24, 72, 168} h.
"""

import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.cli import main

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
D0 = datetime(2030, 1, 1, tzinfo=UTC)
O1 = datetime(2030, 4, 29, tzinfo=UTC)
HOUR = timedelta(hours=1)


@pytest.fixture(scope="module")
def registration():
    from sentira.backtest.registration import load_registration

    return load_registration(EXAMPLES / "synthetic-registration.toml")


def series(topics, *, start=D0, end=O1 + timedelta(days=7)):
    from sentira.series.synthetic import SyntheticSeries

    return SyntheticSeries(start, end, topics, "0" * 64)


def steady(per_hour, *, first=D0, hours=None):
    from sentira.series.episodes import Observation

    hours = int((O1 + timedelta(days=7) - first) / HOUR) if hours is None else hours
    rows = []
    for hour in range(hours):
        published = first + timedelta(hours=hour, minutes=30)
        rows.extend(Observation(published, published) for _ in range(per_hour))
    return rows


def decaying(half_life_hours, starts, *, peak=80, hours=240):
    """Bursts whose hourly count halves every `half_life_hours`, on a zero background."""
    from sentira.series.episodes import Observation

    rows = []
    for start in starts:
        for hour in range(hours):
            count = round(peak * 2 ** (-hour / half_life_hours))
            published = start + timedelta(hours=hour, minutes=30)
            rows.extend(Observation(published, published) for _ in range(count))
    return tuple(rows)


# Episodes on a zero background end at 2 x 168 h; 18-day spacing clears refractory.
BURSTS = [D0 + timedelta(days=days) for days in (30, 48, 66, 84, 102)]


def test_c_min_and_k_floor_follow_registered_rule(registration):
    from sentira.backtest.measurement import measure

    # Hourly volumes are half ones and half threes: median 2, MAD 1, sigma 1.4826.
    # c_min = ceil(24 * 2 + 3 * sqrt(24) * 1.4826) = ceil(69.79) = 70
    # k_floor = ceil(2 * sqrt(24) * 1.4826) = ceil(14.53) = 15
    measured = measure(series({"one": steady(1), "three": steady(3)}), registration)
    assert (measured.hourly_median, measured.hourly_mad) == (2.0, 1.0)
    assert (measured.c_min, measured.k_floor) == (70, 15)
    # No surges: too few half-lives, so the largest registered horizon applies.
    assert measured.half_life_episodes == 0 and measured.half_life_hours is None
    assert measured.horizon_hours == 168
    assert measured.registration_version == registration.version

    quiet = measure(series({"empty": (), "sparse": steady(0)}), registration)
    assert (quiet.hourly_median, quiet.hourly_mad) == (0.0, 0.0)
    assert (quiet.c_min, quiet.k_floor) == (5, 5)


@pytest.mark.parametrize(("half_life", "horizon"), [(6, 24), (20, 72)])
def test_half_life_recovered_on_synthetic_decay(registration, half_life, horizon):
    from sentira.backtest.measurement import measure

    measured = measure(series({"decay": decaying(half_life, BURSTS)}), registration)
    assert measured.half_life_episodes == len(BURSTS)
    # Hourly buckets start at onset, one hour after the first burst hour.
    assert abs(measured.half_life_hours - half_life) <= 1
    assert measured.horizon_hours == horizon
    assert (measured.c_min, measured.k_floor) == (5, 5)


def test_addendum_invariant_to_rows_after_first_origin(registration):
    from sentira.backtest.measurement import measure
    from sentira.series.episodes import Observation

    base = decaying(6, BURSTS) + tuple(steady(1, first=D0, hours=118 * 24))
    later = tuple(Observation(O1 + timedelta(hours=h), O1 + timedelta(hours=h)) for h in range(50))
    late_visible = tuple(
        Observation(O1 - timedelta(hours=h), O1 + timedelta(hours=1)) for h in range(1, 300)
    )
    original = measure(series({"topic": base}), registration)
    assert measure(series({"topic": base + later + late_visible}), registration) == original
    changed = base + (Observation(O1 - timedelta(days=3), O1 - timedelta(days=3)),)
    assert measure(series({"topic": changed}), registration).preorigin_sha256 != (
        original.preorigin_sha256
    )


def test_addendum_refused_until_preorigin_span_complete(registration):
    from sentira.backtest.measurement import measure

    topics = {"topic": decaying(6, BURSTS)}
    with pytest.raises(ValueError, match="pre-origin"):
        measure(series(topics, end=O1 - HOUR), registration)
    assert measure(series(topics, end=O1), registration).half_life_episodes == len(BURSTS)
    with pytest.raises(ValueError, match="history start"):
        measure(series(topics, start=D0 + timedelta(days=1)), registration)


def test_shipped_measured_addendum_reproduces(registration):
    from sentira.backtest.measurement import measure, render_measured
    from sentira.backtest.registration import load_measured
    from sentira.series.synthetic import load_series

    shipped = EXAMPLES / "synthetic-measured.toml"
    measured = measure(load_series(EXAMPLES / "synthetic-series.toml"), registration)
    assert measured == load_measured(shipped)
    assert render_measured(measured) == shipped.read_text(encoding="utf-8")


def workflow(tmp_path):
    registration = tmp_path / "registration.toml"
    shutil.copyfile(EXAMPLES / "synthetic-registration.toml", registration)
    source = tmp_path / "series.toml"
    shutil.copyfile(EXAMPLES / "synthetic-series.toml", source)
    return registration, source, tmp_path / "measured.toml", tmp_path / "registration.lock"


def run_count(registration, measured, lock, source, output):
    return main(
        [
            "count",
            "--registration",
            str(registration),
            "--measured",
            str(measured),
            "--lock",
            str(lock),
            "--series",
            str(source),
            "--output",
            str(output),
        ]
    )


def test_measure_lock_count_workflow(tmp_path):
    registration, source, measured, lock = workflow(tmp_path)
    measure = ["measure", "--registration", str(registration), "--series", str(source)]
    assert main([*measure, "--output", str(measured)]) == 0
    expected = (EXAMPLES / "synthetic-measured.toml").read_bytes()
    assert measured.read_bytes() == expected
    # A measured addendum is written once; it is never replaced in place.
    assert main([*measure, "--output", str(measured)]) == 1
    locking = ["lock", "--registration", str(registration), "--measured", str(measured)]
    assert main([*locking, "--output", str(lock)]) == 0
    assert main([*locking, "--output", str(lock)]) == 1
    output = tmp_path / "count.md"
    assert run_count(registration, measured, lock, source, output) == 0
    assert "SYNTHETIC surge count report" in output.read_text(encoding="utf-8")


def test_count_refuses_when_preorigin_data_differs_from_measurement(tmp_path):
    from sentira.backtest.registration import write_lock

    registration, source, measured, lock = workflow(tmp_path)
    measure = ["measure", "--registration", str(registration), "--series", str(source)]
    assert main([*measure, "--output", str(measured)]) == 0
    write_lock(registration, measured, lock)
    output = tmp_path / "count.md"

    # One more pre-origin segment: the counted series no longer matches the addendum.
    text = source.read_text(encoding="utf-8")
    boundary = ']\n\n[[topics]]\nid = "housing"'
    extra = "  { first = 2030-03-01T00:00:00Z, hours = 2, per_hour = 1 },\n" + boundary
    source.write_text(text.replace(boundary, extra, 1), encoding="utf-8")
    assert run_count(registration, measured, lock, source, output) == 1
    assert not output.exists()

    # A hand-edited threshold, relocked, no longer reproduces from the data.
    source.write_text(text, encoding="utf-8")
    edited = re.sub(r"c_min = (\d+)", lambda m: f"c_min = {int(m[1]) + 1}", measured.read_text())
    measured.write_text(edited, encoding="utf-8")
    lock.unlink()
    write_lock(registration, measured, lock)
    assert run_count(registration, measured, lock, source, output) == 1
    assert not output.exists()


def test_half_life_counts_from_last_peak_to_half_inclusive():
    from sentira.backtest.measurement import half_life
    from sentira.series.episodes import Episode

    onset = D0 + timedelta(days=40)
    # Hourly counts 10, 10, 8, 5, 4 after onset: the last peak is hour 1 and
    # hour 3 is exactly half of the peak, so the half-life is two hours.
    counts = [10, 10, 8, 5, 4]
    published = [
        onset + timedelta(hours=h, minutes=30) for h, n in enumerate(counts) for _ in range(n)
    ]
    episode = Episode(
        onset_at=onset,
        baseline=0.0,
        k=10.0,
        k_floor_binds=True,
        tau_k=None,
        overshoot=None,
        detected_at_crossing=False,
        crossed_2k_at=None,
        resolves_at=None,
        label="below_k",
        ended_at=onset + timedelta(hours=len(counts)),
        end_reason="quiet",
    )
    assert half_life(published, episode, O1) == 2
    flat = [onset + timedelta(hours=h, minutes=30) for h in range(5) for _ in range(3)]
    assert half_life(flat, episode, O1) is None


def test_horizon_is_smallest_registered_value_covering_the_multiple(registration):
    from sentira.backtest.measurement import select_horizon

    surge = registration.surge
    assert select_horizon([8, 8, 8], surge) == (8.0, 24)
    assert select_horizon([8, 9, 9], surge) == (9.0, 72)
    assert select_horizon([60, 60, 60], surge) == (60.0, 168)
    assert select_horizon([1, 1], surge) == (None, 168)
