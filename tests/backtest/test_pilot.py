"""Pilot registration: locked before collection, bound to its frame and inputs."""

import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.backtest.pilot import (
    load_pilot,
    load_pilot_lock,
    pilot_lock_text,
    select_sample,
    write_pilot_lock,
)
from sentira.cli import main
from sentira.config.channels import load_channel_frame
from sentira.config.collection import load_collection_policy
from sentira.config.quota import load_quota_policy
from sentira.config.taxonomy import load_taxonomy
from sentira.config.volume import load_volume

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "examples/synthetic-pilot.toml"
FRAME = ROOT / "examples/synthetic-channels.toml"
POLICY = ROOT / "examples/synthetic-policy.toml"
QUOTA = ROOT / "examples/synthetic-quota.toml"
VOLUME = ROOT / "examples/synthetic-volume.toml"
TAXONOMY = ROOT / "examples/synthetic-taxonomy.toml"
LOCK = ROOT / "examples/synthetic-pilot.lock"
PATHS = (PILOT, FRAME, POLICY, QUOTA, VOLUME, TAXONOMY)
REGISTERED = datetime(2029, 12, 1, tzinfo=UTC)
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


def inputs(pilot=None, taxonomy=None):
    return (
        pilot or load_pilot(PILOT),
        load_channel_frame(FRAME),
        load_collection_policy(POLICY),
        load_quota_policy(QUOTA),
        load_volume(VOLUME),
        taxonomy or load_taxonomy(TAXONOMY),
    )


def lock_text(pilot=None, locked_at=LOCKED_AT, taxonomy=None):
    return pilot_lock_text(*inputs(pilot, taxonomy), locked_at=locked_at, source="declared")


def test_shipped_pilot_validates_and_lock_verifies():
    locked = load_pilot_lock(*PATHS, lock_path=LOCK)
    assert locked.pilot.total_channels == 12
    assert (locked.locked_at, locked.locked_at_source) == (LOCKED_AT, "declared")
    # 12 channels: 768 live units a day for 14 days, plus 28 days of history:
    # 3,360 videos at 3 pages and 12 channels at 6 playlist pages.
    assert locked.projected_units == 768 * 14 + 3360 * 3 + 12 * 6
    assert locked.projected_units <= locked.pilot.quota_ceiling_units
    # The lock records the digest every topic assignment carries.
    assert locked.digests[-1] == locked.taxonomy.sha256
    assert lock_text() == LOCK.read_text(encoding="utf-8")


def test_sample_is_fixed_by_seed_and_frozen_frame():
    pilot, frame = inputs()[:2]
    sample = dict(select_sample(pilot, frame))
    assert sample == dict(select_sample(pilot, frame))
    assert sorted(sample) == ["broadcasters", "institutions", "news-outlets"]
    types = {channel.id: channel.channel_type for channel in frame.channels}
    for stratum in pilot.strata:
        assert len(sample[stratum.name]) == stratum.channels
        assert {types[item] for item in sample[stratum.name]} == {stratum.channel_type}
    reseeded = dict(select_sample(replace(pilot, selection_seed=7), frame))
    assert reseeded != sample


def test_channel_added_after_registration_is_never_sampled():
    pilot, frame = inputs()[:2]
    # Five institutions exist, but the fifth was added after registration.
    assert len([c for c in frame.channels if c.channel_type == "institution"]) == 5
    institutions = dict(select_sample(pilot, frame))["institutions"]
    assert "synthetic-institution-05" not in institutions
    assert len(institutions) == 4


def test_stratum_needs_enough_candidates(tmp_path):
    path = copy(tmp_path, PILOT, "pilot.toml")
    pilot = load_pilot(edit(path, '"broadcaster"\nchannels = 4', '"broadcaster"\nchannels = 9'))
    with pytest.raises(ValueError, match="candidate"):
        select_sample(pilot, load_channel_frame(FRAME))
    other = replace(load_pilot(PILOT), selection_frame_version="another-frame")
    with pytest.raises(ValueError, match="frame"):
        select_sample(other, load_channel_frame(FRAME))


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
        ('"broadcaster"\nchannels = 4', '"broadcaster"\nchannels = 0'),
        ('"broadcaster"\nchannels = 4', '"broadcaster"\nchannels = 53'),
        ('name = "institutions"', 'name = "broadcasters"'),
        ('channel_type = "institution"', 'channel_type = "broadcaster"'),
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
    pilot = load_pilot(PILOT)
    # Direct construction keeps one canonical form, so digests cannot differ by order.
    for adaptations in (pilot.adaptations[::-1], pilot.adaptations[:1] * 2):
        with pytest.raises(ValueError):
            replace(pilot, adaptations=adaptations)


def test_live_days_cover_latency_measurement(tmp_path):
    path = copy(tmp_path, PILOT, "pilot.toml")
    assert load_pilot(edit(path, "live_days = 14", "live_days = 7")).live_days == 7
    with pytest.raises(ValueError):
        load_pilot(edit(path, "live_days = 7", "live_days = 6"))


def test_pilot_lock_window_runs_from_registration_to_collection_start():
    assert lock_text(locked_at=REGISTERED) and lock_text(locked_at=START)
    with pytest.raises(ValueError, match="before any collection"):
        lock_text(locked_at=START + timedelta(seconds=1))
    with pytest.raises(ValueError, match="after registration"):
        lock_text(locked_at=REGISTERED - timedelta(seconds=1))


def test_pilot_lock_binds_a_taxonomy_frozen_before_it():
    taxonomy = load_taxonomy(TAXONOMY)
    assert lock_text(taxonomy=replace(taxonomy, frozen_at=LOCKED_AT))
    late = replace(taxonomy, frozen_at=LOCKED_AT + timedelta(seconds=1))
    with pytest.raises(ValueError, match="frozen"):
        lock_text(taxonomy=late)


def test_pilot_lock_refuses_projected_cost_above_ceiling(tmp_path):
    path = copy(tmp_path, PILOT, "pilot.toml")
    exact = load_pilot(edit(path, "quota_ceiling_units = 30000", "quota_ceiling_units = 20904"))
    assert lock_text(exact)
    short = load_pilot(edit(path, "quota_ceiling_units = 20904", "quota_ceiling_units = 20903"))
    with pytest.raises(ValueError, match="ceiling"):
        lock_text(short)


@pytest.mark.parametrize(
    ("index", "old", "new"),
    [
        (0, "live_days = 14", "live_days = 13"),
        (1, 'id = "synthetic-party-03"', 'id = "synthetic-party-04"'),
        (2, "page_cap = 10", "page_cap = 9"),
        (3, "live = 6000\nretrieval = 3000", "live = 5999\nretrieval = 3001"),
        (4, "threads_per_video = 300", "threads_per_video = 301"),
        (5, '"prensek"', '"prensok"'),
    ],
)
def test_changed_input_refused_after_lock(tmp_path, index, old, new):
    paths = [copy(tmp_path, source, f"{index}-{source.name}") for source in PATHS]
    lock = tmp_path / "pilot.lock"
    write_pilot_lock(*paths, lock_path=lock, locked_at=LOCKED_AT, source="declared")
    assert load_pilot_lock(*paths, lock_path=lock).locked_at == LOCKED_AT
    edit(paths[index], old, new)
    with pytest.raises(ValueError):
        load_pilot_lock(*paths, lock_path=lock)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"projected_units": 20904', '"projected_units": 20000'),
        ('"projected_units": 20904', '"projected_units": 20904.0'),
        ('"locked_at": "2029-12-15T00:00:00+00:00"', '"locked_at": "2030-01-02T00:00:00+00:00"'),
        ('"locked_at": "2029-12-15T00:00:00+00:00"', '"locked_at": 5'),
        ('"locked_at_source": "declared"', '"locked_at_source": "trusted"'),
        ('"synthetic-broadcaster-03"', '"synthetic-broadcaster-02"'),
        ('"sample": {', '"sample": ["x"], "unused": {'),
        ('"schema": 2', '"schema": 1'),
        ('"schema": 2', '"schema": 2.0'),
        ('"schema": 2', '"schema": 2, "note": "x"'),
        ('"taxonomy_sha256": "', '"taxonomy_sha256": "0'),
    ],
)
def test_tampered_lock_record_refused(tmp_path, old, new):
    lock = edit(copy(tmp_path, LOCK, "pilot.lock"), old, new)
    with pytest.raises(ValueError):
        load_pilot_lock(*PATHS, lock_path=lock)


def test_pilot_lock_never_overwritten(tmp_path):
    lock = tmp_path / "pilot.lock"
    write_pilot_lock(*PATHS, lock_path=lock, locked_at=LOCKED_AT, source="declared")
    with pytest.raises(FileExistsError):
        write_pilot_lock(*PATHS, lock_path=lock, locked_at=LOCKED_AT, source="declared")


def arguments(output, *extra):
    return [
        "lock-pilot",
        *("--pilot", str(PILOT), "--channels", str(FRAME), "--policy", str(POLICY)),
        *("--quota", str(QUOTA), "--volume", str(VOLUME), "--taxonomy", str(TAXONOMY)),
        *("--output", str(output)),
        *extra,
    ]


def test_lock_pilot_command(tmp_path):
    output = tmp_path / "new" / "pilot.lock"
    assert main(arguments(output, "--locked-at", "2029-12-15T00:00:00Z")) == 0
    assert output.read_text(encoding="utf-8") == LOCK.read_text(encoding="utf-8")
    assert main(arguments(output, "--locked-at", "2029-12-15T00:00:00Z")) == 1
    assert main(arguments(tmp_path / "late.lock", "--locked-at", "2030-01-02T00:00:00Z")) == 1
    assert main(arguments(PILOT, "--locked-at", "2029-12-15T00:00:00Z")) == 1
    # Without a declared time the system clock is used and labelled as such. The
    # example registration lies in the future, so the clock falls before it.
    assert main(arguments(tmp_path / "early.lock")) == 1
    earlier = edit(
        copy(tmp_path, PILOT, "pilot.toml"),
        "registered_at = 2029-12-01T00:00:00Z",
        "registered_at = 2020-01-01T00:00:00Z",
    )
    frame = copy(tmp_path, FRAME, "channels.toml")
    text = frame.read_text(encoding="utf-8")
    frame.write_text(
        text.replace("added_at = 2029-11-01", "added_at = 2019-11-01"), encoding="utf-8"
    )
    system = tmp_path / "system.lock"
    command = arguments(system)
    command[command.index(str(PILOT))] = str(earlier)
    command[command.index(str(FRAME))] = str(frame)
    # The example taxonomy is frozen in the future too, so the clock refuses it.
    assert main(command) == 1
    taxonomy = edit(
        copy(tmp_path, TAXONOMY, "taxonomy.toml"),
        "frozen_at = 2029-11-15T00:00:00Z",
        "frozen_at = 2019-11-15T00:00:00Z",
    )
    command[command.index(str(TAXONOMY))] = str(taxonomy)
    assert main(command) == 0
    assert json.loads(system.read_text(encoding="utf-8"))["locked_at_source"] == "system"
