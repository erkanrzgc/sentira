"""End-to-end synthetic pilot run under a verified lock; no network, no platform."""

import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.backtest.pilot import load_pilot_lock, write_pilot_lock
from sentira.collectors.pilot_run import (
    ProviderError,
    SimulationClock,
    SyntheticProvider,
    render_run,
    run_pilot,
)
from sentira.collectors.policy import discovery_time
from sentira.storage.quota import QuotaLedger

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "pilot": ROOT / "examples/synthetic-pilot.toml",
    "frame": ROOT / "examples/synthetic-channels.toml",
    "policy": ROOT / "examples/synthetic-policy.toml",
    "quota": ROOT / "examples/synthetic-quota.toml",
    "volume": ROOT / "examples/synthetic-volume.toml",
    "taxonomy": ROOT / "examples/synthetic-taxonomy.toml",
}
START = datetime(2030, 1, 1, tzinfo=UTC)
LOCKED_AT = datetime(2029, 12, 15, tzinfo=UTC)
# A small pilot keeps the simulation fast: one channel per stratum, a week each.
SMALL = {
    "history": ("history_days = 28", "history_days = 7"),
    "live": ("live_days = 14", "live_days = 7"),
    "a": ('"broadcaster"\nchannels = 4', '"broadcaster"\nchannels = 1'),
    "b": ('"news_outlet"\nchannels = 4', '"news_outlet"\nchannels = 1'),
    "c": ('"institution"\nchannels = 4', '"institution"\nchannels = 1'),
}


def locked_pilot(tmp_path, quota_edits=(), **edits):
    paths = {}
    for name, source in SOURCES.items():
        paths[name] = tmp_path / f"{name}.toml"
        shutil.copyfile(source, paths[name])
    changes = [("pilot", old, new) for old, new in {**SMALL, **edits}.values()]
    changes += [("quota", old, new) for old, new in quota_edits]
    for name, old, new in changes:
        text = paths[name].read_text(encoding="utf-8")
        assert old in text
        paths[name].write_text(text.replace(old, new, 1), encoding="utf-8")
    lock = tmp_path / "pilot.lock"
    order = [paths[name] for name in SOURCES]
    write_pilot_lock(*order, lock_path=lock, locked_at=LOCKED_AT, source="declared")
    return load_pilot_lock(*order, lock_path=lock)


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    return locked_pilot(tmp_path_factory.mktemp("pilot"))


@pytest.fixture(scope="module")
def baseline(small):
    # One shared run of the small pilot: the simulation is deterministic.
    return run(small)


def run(locked, *, seed=11, volume=None):
    clock = SimulationClock(LOCKED_AT)
    provider = SyntheticProvider(locked, volume or locked.volume, seed=seed, clock=clock)
    with QuotaLedger(":memory:", locked.quota, clock=clock) as ledger:
        result = run_pilot(locked, provider, ledger, clock)
        debits = ledger.debits()
    return result, provider, debits


def test_pilot_refuses_to_start_without_a_valid_lock(small):
    locked = small
    clock = SimulationClock(LOCKED_AT)
    provider = SyntheticProvider(locked, locked.volume, seed=1, clock=clock)
    with QuotaLedger(":memory:", locked.quota, clock=clock) as ledger:
        with pytest.raises(ValueError, match="lock"):
            run_pilot(None, provider, ledger, clock)
    # A ledger under another quota policy is not the locked one.
    other = replace(locked.quota, version="another-quota")
    with QuotaLedger(":memory:", other, clock=clock) as ledger:
        with pytest.raises(ValueError, match="quota"):
            run_pilot(locked, provider, ledger, clock)
    # Ledger and provider must read the run's own clock and lock.
    other_clock = SimulationClock(LOCKED_AT)
    with QuotaLedger(":memory:", locked.quota, clock=other_clock) as ledger:
        with pytest.raises(ValueError, match="clock"):
            run_pilot(locked, provider, ledger, clock)
    with QuotaLedger(":memory:", locked.quota, clock=clock) as ledger:
        stranger = SyntheticProvider(locked, locked.volume, seed=1, clock=other_clock)
        with pytest.raises(ValueError, match="clock"):
            run_pilot(locked, stranger, ledger, clock)
        with pytest.raises(ValueError, match="provider"):
            run_pilot(locked, lambda endpoint, params: {}, ledger, clock)
    # A run that would start after collection start is refused.
    late = SimulationClock(START + timedelta(hours=1))
    with QuotaLedger(":memory:", locked.quota, clock=late) as ledger:
        with pytest.raises(ValueError, match="collection start"):
            run_pilot(
                locked, SyntheticProvider(locked, locked.volume, seed=1, clock=late), ledger, late
            )


def test_no_call_precedes_the_lock_or_discovery(small, baseline):
    locked = small
    result, provider, debits = baseline
    assert debits and all(debit.debited_at >= START >= locked.locked_at for debit in debits)
    published = provider.published_at
    for endpoint, params, now in provider.log:
        if endpoint == "commentThreads.list" and params["purpose"] == "live":
            assert now >= discovery_time(locked.policy, published[params["video"]])


def test_ledger_units_equal_pilot_calls(baseline, small):
    result, provider, debits = baseline
    # Debits already in the ledger belong to no run and are not counted.
    clock = SimulationClock(LOCKED_AT)
    with QuotaLedger(":memory:", small.quota, clock=clock) as ledger:
        ledger.debit("live", "videos.list")
        fresh = SyntheticProvider(small, small.volume, seed=11, clock=clock)
        assert run_pilot(small, fresh, ledger, clock).units == result.units
    assert len(debits) == len(provider.log) == result.spent
    assert sum(debit.units for debit in debits) == result.spent
    assert result.units == {
        purpose: sum(d.units for d in debits if d.purpose == purpose)
        for purpose in {d.purpose for d in debits}
    }


class FlakyProvider(SyntheticProvider):
    """Fails every seventh call, as a real provider sometimes does."""

    attempts = 0

    def __call__(self, endpoint, params):
        self.attempts += 1
        if self.attempts % 7 == 0:
            raise ProviderError("synthetic failure")
        if self.attempts % 11 == 0:
            raise TimeoutError("synthetic timeout")
        return super().__call__(endpoint, params)


def test_failed_calls_stay_spent_and_the_run_carries_on(small):
    clock = SimulationClock(LOCKED_AT)
    provider = FlakyProvider(small, small.volume, seed=11, clock=clock)
    with QuotaLedger(":memory:", small.quota, clock=clock) as ledger:
        result = run_pilot(small, provider, ledger, clock)
        debits = ledger.debits()
    failed = sum(debit.outcome == "failed" for debit in debits)
    assert result.failed_calls == failed > 0
    assert result.spent == len(debits) == provider.attempts
    assert result.stopped is None
    # Failed retrieval pages are retried, so no channel's history is dropped.
    assert result.retrieval_complete and result.history_videos == 3 * 70
    # Failed discoveries delay a video; no poll may precede its actual discovery.
    for endpoint, params, now in provider.log:
        if endpoint == "commentThreads.list" and params["purpose"] == "live":
            assert now >= result.discovered_at[params["video"]]


def test_provider_pages_through_the_snapshot_a_walk_began_on(small):
    clock = SimulationClock(START)
    provider = SyntheticProvider(small, small.volume, seed=11, clock=clock)
    video, published = min(
        (item for item in provider.published_at.items() if item[1] >= START),
        key=lambda item: item[1],
    )
    clock.advance(published + 2 * timedelta(hours=1))
    params = {"video": video, "page": 0, "purpose": "test"}
    first = provider("commentThreads.list", params)
    snapshot = clock()
    clock.advance(published + 30 * timedelta(hours=1))
    # A walk carrying its snapshot sees the same page; a fresh listing sees more.
    assert provider("commentThreads.list", {**params, "as_of": snapshot}) == first
    assert provider("commentThreads.list", params) != first
    # A snapshot can never reach past the clock.
    future = {**params, "as_of": clock() + timedelta(days=9)}
    assert provider("commentThreads.list", future) == provider("commentThreads.list", params)


def test_retrieval_across_sessions_reads_each_page_once(tmp_path):
    reservations = (("live = 6000\nretrieval = 3000", "live = 8800\nretrieval = 200"),)
    locked = locked_pilot(tmp_path, quota_edits=reservations)
    result, provider, _ = run(locked)
    assert result.retrieval_complete and result.history_videos == 3 * 70
    walks = {}
    for _endpoint, params, _ in provider.log:
        if params["purpose"] == "retrieval":
            key = params.get("video") or params["channel"]
            walks.setdefault(key, []).append((params["as_of"], params["page"]))
    sessions = {as_of.date() for pages in walks.values() for as_of, _ in pages}
    assert len(sessions) > 1
    for pages in walks.values():
        # One snapshot per walk, its pages read once and in order.
        assert len({as_of for as_of, _ in pages}) == 1
        assert [page for _, page in pages] == list(range(len(pages)))
    # Every thread visible at its walk's snapshot is counted once, none twice.
    videos = {key: pages[0][0] for key, pages in walks.items() if key in provider.published_at}
    expected = sum(provider.threads_visible(video, as_of) for video, as_of in videos.items())
    assert result.history_threads == expected


def test_pilot_run_is_deterministic(small, baseline):
    locked = small
    first, second = baseline[0], run(locked)[0]
    assert render_run(first) == render_run(second)
    assert render_run(run(locked, seed=12)[0]) != render_run(first)


def test_executed_cost_matches_projection_on_synthetic_volumes(small, baseline):
    locked = small
    result = baseline[0]
    assert result.stopped is None and result.retrieval_complete
    # Discovery is exact: 3 channels x 4 ticks x 7 days, one page each.
    assert result.calls["playlistItems.list:live"] == 3 * 4 * 7
    # Polls due after the live window, and history threads not yet posted at
    # retrieval, make the executed cost lower than the steady-state projection.
    assert result.polls_beyond_window > 0
    assert result.units["live"] <= result.projected_live_units
    assert result.units["retrieval"] <= result.projected_retrieval_units
    assert result.spent <= locked.projected_units


def test_pilot_stops_cleanly_at_its_ceiling(tmp_path):
    ceiling = ("quota_ceiling_units = 30000", "quota_ceiling_units = 2500")
    locked = locked_pilot(tmp_path, ceiling=ceiling)
    # The world is busier than the locked assumptions: ten times the threads.
    heavy = replace(locked.volume, thread_strata=((1.0, 3000),))
    result, provider, debits = run(locked, volume=heavy)
    assert result.stopped == "pilot_ceiling"
    assert result.spent <= locked.pilot.quota_ceiling_units
    assert result.spent == len(debits) == len(provider.log)
    assert "stopped at the pilot ceiling" in render_run(result)


def test_report_labels_figures_as_simulated(small, baseline):
    locked = small
    report = render_run(baseline[0])
    assert "simulated" in report and "no platform was contacted" in report
    assert locked.digests[0] in report
