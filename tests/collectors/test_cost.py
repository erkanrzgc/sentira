"""Quota cost projection under policy P; every figure is calculated from assumptions."""

from fractions import Fraction
from pathlib import Path

import pytest

from sentira.cli import main
from sentira.collectors.cost import project, render_cost
from sentira.config.collection import load_collection_policy
from sentira.config.quota import load_quota_policy
from sentira.config.volume import load_volume

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "examples/synthetic-policy.toml"
QUOTA = ROOT / "examples/synthetic-quota.toml"
VOLUME = ROOT / "examples/synthetic-volume.toml"


def edited(tmp_path, source, name, **replacements):
    text = source.read_text(encoding="utf-8")
    for old, new in replacements.values():
        assert old in text
        text = text.replace(old, new, 1)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def shipped():
    return (
        load_collection_policy(POLICY),
        load_quota_policy(QUOTA),
        load_volume(VOLUME),
    )


def test_shipped_projection_matches_documented_arithmetic():
    result = project(*shipped())
    # 60 channels x 4 discovery ticks; 600 videos x 6 single-page polls.
    assert (result.videos_per_day, result.discovery_units) == (600, 240)
    assert (result.poll_pages_per_video, result.poll_units) == (6, 3600)
    assert (result.live_units, result.live_reservation) == (3840, 6000)
    assert result.lost_threads_per_day == 0
    # 600 videos x 365 days x 3 pages, plus 73 playlist pages per channel-year.
    assert result.retrieval_units_per_history_year == 661_380
    assert result.retrieval_days_per_history_year == 221


def test_projection_uses_the_registered_schedule(tmp_path):
    policy = load_collection_policy(
        edited(
            tmp_path,
            POLICY,
            "policy.toml",
            interval=("discovery_interval_hours = 6", "discovery_interval_hours = 12"),
            ages=("[1, 6, 24, 72, 168, 720]", "[1, 6]"),
        )
    )
    volume = load_volume(
        edited(
            tmp_path,
            VOLUME,
            "volume.toml",
            threads=("threads_per_video = 300", "threads_per_video = 100"),
            shares=("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[0.5, 1.0]"),
        )
    )
    result = project(policy, load_quota_policy(QUOTA), volume)
    # Half of each 12-hour discovery interval is seen after the 6-hour age: one
    # coalesced poll instead of two, so 1.5 polls per video on average.
    assert result.poll_pages_per_video == Fraction(3, 2)
    assert result.poll_units == 900
    assert result.discovery_units == 60 * 2
    assert "1.50 pages per video" in render_cost(result)


def test_page_cap_bounds_poll_cost_and_reports_lost_threads(tmp_path):
    volume = load_volume(
        edited(
            tmp_path,
            VOLUME,
            "volume.toml",
            threads=("threads_per_video = 300", "threads_per_video = 5000"),
            shares=("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]"),
        )
    )
    result = project(load_collection_policy(POLICY), load_quota_policy(QUOTA), volume)
    # The first poll meets 2,500 new threads: 10 pages and 1,500 threads lost.
    # The other five meet 500 each: 5 pages, nothing lost.
    assert result.poll_pages_per_video == 10 + 5 * 5
    assert result.lost_threads_per_day == 600 * 1500


def test_every_call_costs_a_page_even_when_nothing_is_new(tmp_path):
    volume = load_volume(
        edited(
            tmp_path,
            VOLUME,
            "volume.toml",
            videos=("videos_per_channel_day = 10", "videos_per_channel_day = 0"),
            threads=("threads_per_video = 300", "threads_per_video = 100"),
            shares=("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[0.5, 1.0, 1.0, 1.0, 1.0, 1.0]"),
        )
    )
    result = project(load_collection_policy(POLICY), load_quota_policy(QUOTA), volume)
    # Four polls find nothing new and still spend a unit each; so does discovery.
    assert result.poll_pages_per_video == 6
    assert result.discovery_units == 60 * 4


def test_live_overrun_is_reported_not_hidden(tmp_path):
    volume = load_volume(
        edited(tmp_path, VOLUME, "volume.toml", channels=("channels = 60", "channels = 200"))
    )
    result = project(load_collection_policy(POLICY), load_quota_policy(QUOTA), volume)
    assert result.live_units == 200 * 4 + 2000 * 6
    assert result.live_units > result.live_reservation
    report = render_cost(result)
    assert "exceeds the live reservation by 6,800 units" in report


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("channels = 60", "channels = 0"),
        ("threads_per_video = 300", "threads_per_video = -1"),
        ("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[0.30, 0.20, 0.85, 0.95, 0.98, 1.00]"),
        ("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[0.30, 0.60, 0.85, 0.95, 0.98, 1.10]"),
        ("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[true, 0.60, 0.85, 0.95, 0.98, 1.00]"),
        ("playlist_page_size = 50", "playlist_page_size = 51"),
        ('mode = "synthetic"', 'mode = "live"'),
        ("playlist_page_size = 50", "playlist_page_size = 50\nspare = 1"),
        ("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "0.5"),
    ],
)
def test_invalid_volume_assumptions_are_refused(tmp_path, old, new):
    with pytest.raises(ValueError):
        load_volume(edited(tmp_path, VOLUME, "volume.toml", change=(old, new)))


def test_missing_retrieval_reservation_is_reported(tmp_path):
    quota = load_quota_policy(
        edited(
            tmp_path,
            QUOTA,
            "quota.toml",
            live=("live = 6000", "live = 9000"),
            retrieval=("retrieval = 3000", "retrieval = 0"),
        )
    )
    result = project(load_collection_policy(POLICY), quota, load_volume(VOLUME))
    assert result.retrieval_days_per_history_year is None
    assert "**no retrieval reservation**" in render_cost(result)
    with pytest.raises(ValueError):
        project(None, quota, load_volume(VOLUME))
    with pytest.raises(ValueError):
        render_cost(None)


def test_shares_must_match_poll_ages(tmp_path):
    volume = load_volume(
        edited(
            tmp_path,
            VOLUME,
            "volume.toml",
            shares=("[0.30, 0.60, 0.85, 0.95, 0.98, 1.00]", "[0.30, 0.60, 1.00]"),
        )
    )
    with pytest.raises(ValueError, match="poll age"):
        project(load_collection_policy(POLICY), load_quota_policy(QUOTA), volume)


def test_report_labels_every_figure_calculated():
    result = project(*shipped())
    report = render_cost(result)
    assert report == render_cost(project(*shipped()))
    assert "Every figure below is *calculated*" in report
    assert "within the live reservation (2,160 units spare)" in report
    assert "221 days of retrieval per history-year" in report
    for digest in (result.policy_sha256, result.quota_sha256, result.volume_sha256):
        assert digest in report
    assumption_rows = [line for line in report.splitlines() if line.startswith("| Assumed")]
    assert len(assumption_rows) == 4


def arguments(output):
    return [
        "cost",
        "--policy",
        str(POLICY),
        "--quota",
        str(QUOTA),
        "--volume",
        str(VOLUME),
        "--output",
        str(output),
    ]


def test_cost_command_writes_report_and_refuses_overwrite(tmp_path):
    output = tmp_path / "cost.md"
    assert main(arguments(output)) == 0
    first = output.read_text(encoding="utf-8")
    assert "3,840" in first
    assert main(arguments(output)) == 1
    assert main([*arguments(output), "--overwrite"]) == 0
    assert output.read_text(encoding="utf-8") == first
    assert main(arguments(tmp_path / "cost.txt")) == 1
