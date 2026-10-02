"""Pilot registration: locked before collection, bound to policy, quota and volume."""

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.backtest.pilot import (
    load_pilot,
    load_pilot_lock,
    pilot_lock_text,
    write_pilot_lock,
)
from sentira.cli import main
from sentira.config.collection import load_collection_policy
from sentira.config.quota import load_quota_policy
from sentira.config.volume import load_volume

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "examples/synthetic-pilot.toml"
POLICY = ROOT / "examples/synthetic-policy.toml"
QUOTA = ROOT / "examples/synthetic-quota.toml"
VOLUME = ROOT / "examples/synthetic-volume.toml"
LOCK = ROOT / "examples/synthetic-pilot.lock"
START = datetime(2030, 1, 1, tzinfo=UTC)
LOCKED_AT = datetime(2029, 12, 15, tzinfo=UTC)


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return path


def copy(tmp_path, source, name):
    target = tmp_path / name
    shutil.copyfile(source, target)
    return target


def others():
    return load_collection_policy(POLICY), load_quota_policy(QUOTA), load_volume(VOLUME)


def test_shipped_pilot_validates_and_lock_verifies():
    locked = load_pilot_lock(PILOT, POLICY, QUOTA, VOLUME, LOCK)
    assert locked.pilot.total_channels == 12
    assert locked.locked_at == LOCKED_AT
    # 12 channels: 768 live units a day for 14 days, plus 28 days of history.
    assert locked.projected_units == 768 * 14 + 10_148
    assert locked.projected_units <= locked.pilot.quota_ceiling_units
    text = pilot_lock_text(load_pilot(PILOT), *others(), locked_at=LOCKED_AT)
    assert text == LOCK.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            'channel_type = "broadcaster"\n',
            'channel_type = "broadcaster"\nmin_subscribers = 1000\n',
        ),
        ("seed = 20300101\n", "seed = 20300101\nmin_views = 10\n"),
        ("live_days = 14\n", "live_days = 14\ntrending_only = true\n"),
    ],
)
def test_selection_schema_has_no_place_for_a_counter(tmp_path, old, new):
    with pytest.raises(ValueError):
        load_pilot(edit(copy(tmp_path, PILOT, "pilot.toml"), old, new))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("registered_at = 2029-12-01T00:00:00Z", "registered_at = 2030-01-02T00:00:00Z"),
        ("history_days = 28", "history_days = 91"),
        (
            'channels = 4\n\n[[strata]]\nname = "news-outlets"',
            'channels = 0\n\n[[strata]]\nname = "news-outlets"',
        ),
        (
            'channels = 4\n\n[[strata]]\nname = "news-outlets"',
            'channels = 53\n\n[[strata]]\nname = "news-outlets"',
        ),
        ('name = "institutions"', 'name = "broadcasters"'),
        ('method = "seeded_random"', 'method = "hand_picked"'),
        ("quota_ceiling_units = 30000", "quota_ceiling_units = 0"),
        ('mode = "synthetic"', 'mode = "live"'),
    ],
)
def test_invalid_pilots_are_refused(tmp_path, old, new):
    with pytest.raises(ValueError):
        load_pilot(edit(copy(tmp_path, PILOT, "pilot.toml"), old, new))


def test_unknown_adaptation_refused(tmp_path):
    path = edit(
        copy(tmp_path, PILOT, "pilot.toml"),
        '"shorten_history_to_ceiling"]',
        '"shorten_history_to_ceiling", "relax_k_min"]',
    )
    with pytest.raises(ValueError):
        load_pilot(path)


def test_live_days_cover_latency_measurement(tmp_path):
    path = copy(tmp_path, PILOT, "pilot.toml")
    assert load_pilot(edit(path, "live_days = 14", "live_days = 7")).live_days == 7
    with pytest.raises(ValueError):
        load_pilot(edit(path, "live_days = 7", "live_days = 6"))


def test_pilot_lock_refused_after_collection_start():
    pilot = load_pilot(PILOT)
    assert pilot_lock_text(pilot, *others(), locked_at=START)
    with pytest.raises(ValueError, match="before"):
        pilot_lock_text(pilot, *others(), locked_at=START + timedelta(seconds=1))


def test_pilot_lock_refuses_projected_cost_above_ceiling(tmp_path):
    path = copy(tmp_path, PILOT, "pilot.toml")
    exact = load_pilot(edit(path, "quota_ceiling_units = 30000", "quota_ceiling_units = 20900"))
    assert pilot_lock_text(exact, *others(), locked_at=LOCKED_AT)
    short = load_pilot(edit(path, "quota_ceiling_units = 20900", "quota_ceiling_units = 20899"))
    with pytest.raises(ValueError, match="ceiling"):
        pilot_lock_text(short, *others(), locked_at=LOCKED_AT)


@pytest.mark.parametrize(
    ("name", "old", "new"),
    [
        ("pilot", "live_days = 14", "live_days = 13"),
        ("policy", "page_cap = 10", "page_cap = 9"),
        ("quota", "live = 6000\nretrieval = 3000", "live = 5999\nretrieval = 3001"),
        ("volume", "threads_per_video = 300", "threads_per_video = 301"),
    ],
)
def test_changed_policy_quota_or_volume_refused_after_lock(tmp_path, name, old, new):
    paths = {
        "pilot": copy(tmp_path, PILOT, "pilot.toml"),
        "policy": copy(tmp_path, POLICY, "policy.toml"),
        "quota": copy(tmp_path, QUOTA, "quota.toml"),
        "volume": copy(tmp_path, VOLUME, "volume.toml"),
    }
    order = [paths[key] for key in ("pilot", "policy", "quota", "volume")]
    lock = tmp_path / "pilot.lock"
    write_pilot_lock(*order, lock, locked_at=LOCKED_AT)
    assert load_pilot_lock(*order, lock).locked_at == LOCKED_AT
    edit(paths[name], old, new)
    with pytest.raises(ValueError):
        load_pilot_lock(*order, lock)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"projected_units": 20900', '"projected_units": 20000'),
        ('"locked_at": "2029-12-15T00:00:00+00:00"', '"locked_at": "2030-01-02T00:00:00+00:00"'),
        ('"schema": 1', '"schema": 2'),
        ('"schema": 1', '"schema": 1, "note": "x"'),
        ('"locked_at": "2029-12-15T00:00:00+00:00"', '"locked_at": 5'),
    ],
)
def test_tampered_lock_record_refused(tmp_path, old, new):
    lock = edit(copy(tmp_path, LOCK, "pilot.lock"), old, new)
    with pytest.raises(ValueError):
        load_pilot_lock(PILOT, POLICY, QUOTA, VOLUME, lock)


def test_pilot_lock_never_overwritten(tmp_path):
    lock = tmp_path / "pilot.lock"
    write_pilot_lock(PILOT, POLICY, QUOTA, VOLUME, lock, locked_at=LOCKED_AT)
    with pytest.raises(FileExistsError):
        write_pilot_lock(PILOT, POLICY, QUOTA, VOLUME, lock, locked_at=LOCKED_AT)


def arguments(output, locked_at="2029-12-15T00:00:00Z"):
    return [
        "lock-pilot",
        *("--pilot", str(PILOT), "--policy", str(POLICY)),
        *("--quota", str(QUOTA), "--volume", str(VOLUME)),
        *("--locked-at", locked_at, "--output", str(output)),
    ]


def test_lock_pilot_command(tmp_path):
    output = tmp_path / "pilot.lock"
    assert main(arguments(output)) == 0
    assert output.read_text(encoding="utf-8") == LOCK.read_text(encoding="utf-8")
    assert main(arguments(output)) == 1
    assert main(arguments(tmp_path / "late.lock", "2030-01-02T00:00:00Z")) == 1
    assert main(arguments(PILOT)) == 1
