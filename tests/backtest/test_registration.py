"""Locked synthetic surge definitions; no collection, network or model calls."""

import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "examples/synthetic-registration.toml"
MEASURED = ROOT / "examples/synthetic-measured.toml"
LOCK = ROOT / "examples/synthetic-registration.lock"


def copies(tmp_path):
    registration = tmp_path / "registration.toml"
    measured = tmp_path / "measured.toml"
    shutil.copyfile(REGISTRATION, registration)
    shutil.copyfile(MEASURED, measured)
    return registration, measured, tmp_path / "registration.lock"


def rewrite(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_shipped_synthetic_registration_validates():
    from sentira.backtest.registration import Cell, load_locked

    locked = load_locked(REGISTRATION, MEASURED, LOCK)
    assert locked.registration.mode == "synthetic"
    assert locked.primary_cell == Cell(2.0, 1.0, 72)
    assert len(locked.grid) == 3 * 4 * 3
    assert len(locked.registration_sha256) == len(locked.measured_sha256) == 64


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('mode = "synthetic"', 'mode = "live"'),
        ("baseline_days = 28", "baseline_days = 28\nbaseline_weeks = 4"),
        ("trailing_hours = 24\n", ""),
        ("calendar_utc_offset_minutes = 0", "calendar_utc_offset_minutes = 7"),
        ("registered_at = 2030-01-01T00:00:00Z", "registered_at = 2030-01-01T00:00:00"),
        ("onset_multipliers = [1.5, 2.0, 3.0]", "onset_multipliers = [1.5, 1.5]"),
        ("horizons_hours = [24, 72, 168]", "horizons_hours = []"),
        ("size_multipliers = [0.5, 1.0, 2.0, 4.0]", "size_multipliers = [-0.5, 1.0, 2.0, 4.0]"),
        ("k_min = 100", "k_min = 10"),
        ("week_floor = 20", "week_floor = true"),
    ],
)
def test_unknown_or_missing_fields_rejected(tmp_path, old, new):
    from sentira.backtest.registration import load_registration

    registration, _, _ = copies(tmp_path)
    rewrite(registration, old, new)
    with pytest.raises(ValueError):
        load_registration(registration)


@pytest.mark.parametrize(
    ("path_index", "old", "new"),
    [
        (0, "onset_multiplier = 2.0", "onset_multiplier = 2.5"),
        (0, "size_multiplier = 1.0", "size_multiplier = 3.0"),
        (0, "few_positives_size_multiplier = 0.5", "few_positives_size_multiplier = 0.25"),
        (0, "few_negatives_size_multiplier = 2.0", "few_negatives_size_multiplier = 8.0"),
        (1, "horizon_hours = 72", "horizon_hours = 48"),
        (1, 'registration_version = "synthetic-surge-1"', 'registration_version = "other"'),
    ],
)
def test_primary_and_fallback_cells_must_be_in_grid(tmp_path, path_index, old, new):
    from sentira.backtest.registration import write_lock

    paths = copies(tmp_path)
    rewrite(paths[path_index], old, new)
    with pytest.raises(ValueError):
        write_lock(*paths)
    assert not paths[2].exists()


def test_lock_refuses_to_overwrite(tmp_path):
    from sentira.backtest.registration import load_locked, write_lock

    registration, measured, lock = copies(tmp_path)
    write_lock(registration, measured, lock)
    original = lock.read_bytes()
    with pytest.raises(FileExistsError):
        write_lock(registration, measured, lock)
    assert lock.read_bytes() == original
    assert load_locked(registration, measured, lock).registration.version == "synthetic-surge-1"


def test_modified_registration_refused_after_lock(tmp_path):
    from sentira.backtest.registration import load_locked, write_lock

    registration, measured, lock = copies(tmp_path)
    write_lock(registration, measured, lock)
    rewrite(registration, "refractory_hours = 72", "refractory_hours = 48")
    with pytest.raises(ValueError, match="registration"):
        load_locked(registration, measured, lock)


def test_modified_measured_addendum_refused_after_lock(tmp_path):
    from sentira.backtest.registration import load_locked, write_lock

    registration, measured, lock = copies(tmp_path)
    write_lock(registration, measured, lock)
    rewrite(measured, "k_floor = 10", "k_floor = 12")
    with pytest.raises(ValueError, match="addendum"):
        load_locked(registration, measured, lock)


def test_lock_ignores_comments_and_line_endings_but_not_definitions(tmp_path):
    from sentira.backtest.registration import load_locked, write_lock

    registration, measured, lock = copies(tmp_path)
    write_lock(registration, measured, lock)
    raw = registration.read_bytes().replace(b"\n", b"\r\n") + b"# trailing note\r\n"
    registration.write_bytes(raw)
    locked = load_locked(registration, measured, lock)
    assert locked.primary_cell.horizon_hours == 72
    recorded = json.loads(lock.read_text(encoding="utf-8"))
    assert recorded["registration_sha256"] == locked.registration_sha256
    assert recorded["measured_sha256"] == locked.measured_sha256


@pytest.mark.parametrize(
    "content",
    ["not json", '{"schema": 2, "registration_sha256": "", "measured_sha256": ""}', "[]"],
)
def test_unreadable_or_foreign_lock_refused(tmp_path, content):
    from sentira.backtest.registration import load_locked

    registration, measured, lock = copies(tmp_path)
    lock.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_locked(registration, measured, lock)
