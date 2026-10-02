"""Per-cell surge counts and the registered selection rule; synthetic input only."""

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.cli import main

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
START = datetime(2030, 1, 1, tzinfo=UTC)
DAY = START + timedelta(days=28)
HOUR = timedelta(hours=1)


@pytest.fixture(scope="module")
def locked():
    from sentira.backtest.registration import load_locked

    return load_locked(
        EXAMPLES / "synthetic-registration.toml",
        EXAMPLES / "synthetic-measured.toml",
        EXAMPLES / "synthetic-registration.lock",
    )


def rows(first, hours, per_hour, *, visible_at=None):
    from sentira.series.episodes import Observation

    published = [
        first + timedelta(hours=h, minutes=30) for h in range(hours) for _ in range(per_hour)
    ]
    return tuple(Observation(p, visible_at or p) for p in published)


def count(cell, **values):
    from sentira.backtest.positives import CellCount

    fields = dict(
        episodes=0,
        eligible=0,
        positive=0,
        negative=0,
        censored=0,
        detected_at_crossing=0,
        k_floor_binds=0,
        positive_weeks=0,
    )
    fields.update(values)
    return CellCount(cell, **fields)


def test_counts_match_hand_labelled_fixture(locked):
    from sentira.backtest.positives import count_cell

    # Zero baselines make each label hand-checkable: k = k_floor = 10 and
    # H = 72 h in the primary cell (see tests/series/test_episodes.py).
    end = DAY + timedelta(days=12)
    series = {
        "negative": rows(DAY, 12, 2),
        "positive": rows(DAY, 20, 2),
        "detected": rows(DAY, 3, 2) + rows(DAY + 3 * HOUR, 10, 2, visible_at=DAY + 13 * HOUR),
        "censored": rows(end - timedelta(days=2), 20, 2),
        "quiet": rows(DAY, 2, 2),
    }
    result = count_cell(series, locked, locked.primary_cell, start=START, end=end)
    assert result.cell == locked.primary_cell
    assert (result.episodes, result.eligible) == (4, 4)
    assert (result.positive, result.negative, result.censored) == (1, 1, 1)
    assert result.detected_at_crossing == 1
    assert result.k_floor_binds == 4
    assert result.positive_weeks == 1


def test_fallback_cell_chosen_by_registered_rule(locked):
    from sentira.backtest.positives import select_cell

    primary = locked.primary_cell
    few_positives = type(primary)(primary.onset_multiplier, 0.5, primary.horizon_hours)
    few_negatives = type(primary)(primary.onset_multiplier, 2.0, primary.horizon_hours)
    enough = dict(positive=100, negative=100, positive_weeks=20)

    chosen = select_cell([count(primary, **enough)], locked)
    assert (chosen.outcome, chosen.cell) == ("primary", primary)

    counts = [count(primary, positive=99, negative=150, positive_weeks=30)]
    counts.append(count(few_positives, **enough))
    chosen = select_cell(counts, locked)
    assert (chosen.outcome, chosen.cell) == ("fallback_few_positives", few_positives)

    counts = [count(primary, positive=150, negative=99, positive_weeks=30)]
    counts.append(count(few_negatives, **enough))
    chosen = select_cell(counts, locked)
    assert (chosen.outcome, chosen.cell) == ("fallback_few_negatives", few_negatives)

    counts = [count(primary, positive=99, negative=99, positive_weeks=30)]
    counts += [count(few_positives, **enough), count(few_negatives, **enough)]
    chosen = select_cell(counts, locked)
    assert (chosen.outcome, chosen.cell) == ("not_backtestable", None)

    counts = [count(primary, positive=99, negative=150, positive_weeks=30)]
    counts.append(count(few_positives, positive=100, negative=99, positive_weeks=30))
    assert select_cell(counts, locked).outcome == "not_backtestable"

    with pytest.raises(ValueError):
        select_cell([count(few_positives, **enough)], locked)


def test_week_floor_enforced(locked):
    from sentira.backtest.positives import select_cell

    primary = locked.primary_cell
    short = select_cell([count(primary, positive=200, negative=200, positive_weeks=19)], locked)
    assert short.outcome == "not_backtestable"
    assert "week floor" in short.reason
    met = select_cell([count(primary, positive=200, negative=200, positive_weeks=20)], locked)
    assert met.outcome == "primary"


def lock_copies(tmp_path):
    from sentira.backtest.registration import write_lock

    registration = tmp_path / "registration.toml"
    measured = tmp_path / "measured.toml"
    shutil.copyfile(EXAMPLES / "synthetic-registration.toml", registration)
    shutil.copyfile(EXAMPLES / "synthetic-measured.toml", measured)
    lock = tmp_path / "registration.lock"
    write_lock(registration, measured, lock)
    return registration, measured, lock


def arguments(registration, measured, lock, output, series=EXAMPLES / "synthetic-series.toml"):
    return [
        "count",
        "--registration",
        str(registration),
        "--measured",
        str(measured),
        "--lock",
        str(lock),
        "--series",
        str(series),
        "--output",
        str(output),
    ]


def test_count_refuses_on_registration_hash_mismatch(tmp_path, capsys):
    registration, measured, lock = lock_copies(tmp_path)
    output = tmp_path / "count.md"
    text = registration.read_text(encoding="utf-8")
    registration.write_text(text.replace("refractory_hours = 72", "refractory_hours = 24"))
    assert main(arguments(registration, measured, lock, output)) == 1
    assert not output.exists()
    assert "refractory" not in capsys.readouterr().err

    registration.write_text(text, encoding="utf-8")
    measured.write_text(measured.read_text().replace("c_min = 6", "c_min = 5"))
    assert main(arguments(registration, measured, lock, output)) == 1
    assert not output.exists()
