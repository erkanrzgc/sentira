"""Collection policy P: deterministic polling schedule and replay visibility."""

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.collectors.policy import (
    discovery_time,
    nominal_poll_times,
    poll_jobs,
    replay_times,
)
from sentira.config.collection import CollectionPolicy, load_collection_policy

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "examples/synthetic-policy.toml"
HOUR = timedelta(hours=1)
P = datetime(2030, 1, 1, 2, 30, tzinfo=UTC)
AGES = (1, 6, 24, 72, 168, 720)


@pytest.fixture(scope="module")
def policy():
    return load_collection_policy(POLICY_PATH)


def edited_policy(tmp_path, **replacements):
    text = POLICY_PATH.read_text(encoding="utf-8")
    for old, new in replacements.values():
        assert old in text
        text = text.replace(old, new, 1)
    path = tmp_path / "policy.toml"
    path.write_text(text, encoding="utf-8")
    return load_collection_policy(path)


def small_policy(tmp_path, page_size, page_cap):
    return edited_policy(
        tmp_path,
        size=("page_size = 100", f"page_size = {page_size}"),
        cap=("page_cap = 10", f"page_cap = {page_cap}"),
    )


def test_shipped_policy_validates(policy):
    assert policy.discovery_interval_hours == 6
    assert policy.poll_ages_hours == AGES
    assert (policy.page_size, policy.page_cap) == (100, 10)
    assert len(policy.sha256) == 64
    # Direct construction is validated as strictly as loading.
    with pytest.raises(ValueError):
        CollectionPolicy("live", "x", 6, AGES, 100, 10)
    with pytest.raises(ValueError):
        CollectionPolicy("synthetic", "x", 6, (), 100, 10)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("discovery_interval_hours = 6", "discovery_interval_hours = 5"),
        ("discovery_interval_hours = 6", "discovery_interval_hours = 0"),
        ("[1, 6, 24, 72, 168, 720]", "[1, 24, 6]"),
        ("[1, 6, 24, 72, 168, 720]", "[1, 6, 6]"),
        ("[1, 6, 24, 72, 168, 720]", "[]"),
        ("[1, 6, 24, 72, 168, 720]", "[0, 6]"),
        ("[1, 6, 24, 72, 168, 720]", "6"),
        ("page_size = 100", "page_size = 101"),
        ("page_cap = 10", "page_cap = 0"),
        ('mode = "synthetic"', 'mode = "live"'),
        ("page_cap = 10", "page_cap = 10\nretry = 1"),
    ],
)
def test_invalid_policies_are_refused(tmp_path, old, new):
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "policy.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        load_collection_policy(path)


def test_discovery_follows_registered_ticks(policy):
    assert discovery_time(policy, P) == datetime(2030, 1, 1, 6, tzinfo=UTC)
    on_tick = datetime(2030, 1, 1, 6, tzinfo=UTC)
    assert discovery_time(policy, on_tick) == on_tick
    late = datetime(2030, 1, 1, 23, 59, tzinfo=UTC)
    assert discovery_time(policy, late) == datetime(2030, 1, 2, tzinfo=UTC)


def test_no_poll_before_discovery(policy):
    discovered = P + 3.5 * HOUR
    jobs = poll_jobs(policy, P, discovered_at=discovered)
    assert all(job.due_at >= discovered for job in jobs)
    first = jobs[0]
    assert (first.ages_hours, first.due_at, first.missed_ages_hours) == ((1,), discovered, (1,))
    with pytest.raises(ValueError):
        poll_jobs(policy, P, discovered_at=P - HOUR)


def test_late_discovery_coalesces_missed_ages(policy):
    discovered = P + 30 * HOUR
    jobs = poll_jobs(policy, P, discovered_at=discovered)
    assert [job.ages_hours for job in jobs] == [(1, 6, 24), (72,), (168,), (720,)]
    assert jobs[0].due_at == discovered
    assert jobs[0].missed_ages_hours == (1, 6, 24)
    assert [job.missed_ages_hours for job in jobs[1:]] == [(), (), ()]


def test_future_ages_anchored_to_publication(policy):
    late = poll_jobs(policy, P, discovered_at=P + 30 * HOUR)
    assert [job.due_at for job in late[1:]] == [P + 72 * HOUR, P + 168 * HOUR, P + 720 * HOUR]
    on_time = poll_jobs(policy, P, discovered_at=P + 0.5 * HOUR)
    assert [job.due_at for job in on_time] == [P + age * HOUR for age in AGES]
    assert all(job.missed_ages_hours == () for job in on_time)


def test_restart_preserves_completed_jobs(policy):
    jobs = poll_jobs(
        policy, P, discovered_at=P + 0.5 * HOUR, completed=(1,), resumed_at=P + 30 * HOUR
    )
    assert [job.ages_hours for job in jobs] == [(6, 24), (72,), (168,), (720,)]
    assert jobs[0].due_at == P + 30 * HOUR
    assert all(1 not in job.ages_hours for job in jobs)
    finished = poll_jobs(policy, P, discovered_at=P, completed=AGES, resumed_at=P + 721 * HOUR)
    assert finished == ()
    for completed in ((2,), (True,)):
        with pytest.raises(ValueError):
            poll_jobs(policy, P, discovered_at=P, completed=completed, resumed_at=P + 30 * HOUR)
    # An age cannot have been completed before it was due.
    with pytest.raises(ValueError):
        poll_jobs(policy, P, discovered_at=P, completed=(720,), resumed_at=P + 30 * HOUR)


def test_catch_up_after_last_age_is_live_only(policy):
    (catch_up,) = poll_jobs(policy, P, discovered_at=P + 800 * HOUR)
    assert catch_up.ages_hours == AGES and catch_up.live_only
    # Discovery exactly at the last age polls it on time: covered, not missed.
    (on_time,) = poll_jobs(policy, P, discovered_at=P + 720 * HOUR)
    assert on_time.ages_hours == AGES and not on_time.live_only
    assert on_time.missed_ages_hours == AGES[:-1]
    # Replay follows the registered schedule, never a late live catch-up.
    nominal = poll_jobs(policy, P, discovered_at=discovery_time(policy, P))
    assert nominal_poll_times(policy, P) == tuple(job.due_at for job in nominal)
    assert not any(job.live_only for job in nominal)


def test_catch_up_never_counts_as_a_replay_poll(tmp_path):
    # Discovery every 12 h with a last age of 6 h: some videos are first seen late.
    policy = edited_policy(
        tmp_path,
        interval=("discovery_interval_hours = 6", "discovery_interval_hours = 12"),
        ages=("[1, 6, 24, 72, 168, 720]", "[1, 6]"),
    )
    early = datetime(2030, 1, 1, 0, 0, 1, tzinfo=UTC)
    (job,) = poll_jobs(policy, early, discovered_at=discovery_time(policy, early))
    assert job.live_only and nominal_poll_times(policy, early) == ()
    thread = early + 5 * HOUR
    assert replay_times(policy, early, [thread], latency=timedelta(0)) == (None,)
    late = datetime(2030, 1, 1, 11, tzinfo=UTC)
    noon = datetime(2030, 1, 1, 12, tzinfo=UTC)
    assert nominal_poll_times(policy, late) == (noon, late + 6 * HOUR)


def test_unrepresentable_times_are_refused(policy):
    edge = datetime(9999, 12, 31, 20, tzinfo=UTC)
    with pytest.raises(ValueError):
        discovery_time(policy, edge)
    with pytest.raises(ValueError):
        poll_jobs(policy, edge, discovered_at=edge)


def test_row_beyond_page_cap_never_replay_visible(tmp_path):
    policy = small_policy(tmp_path, page_size=2, page_cap=2)
    burst = [P + timedelta(minutes=minute) for minute in (1, 30, 60, 90, 120, 150)]
    later = P + 4.5 * HOUR
    times = replay_times(policy, P, [*burst, later], latency=timedelta(0))
    first_poll = datetime(2030, 1, 1, 6, tzinfo=UTC)
    # The poll at discovery returns the newest four; the two oldest are behind the cap.
    assert times[:2] == (None, None)
    assert times[2:6] == (first_poll,) * 4
    assert times[6] == P + 6 * HOUR


def test_row_after_last_poll_age_never_replay_visible(tmp_path):
    policy = small_policy(tmp_path, page_size=2, page_cap=2)
    last = P + 720 * HOUR
    comments = [P + 200 * HOUR, last, last + timedelta(minutes=1)]
    latency = timedelta(minutes=7)
    assert replay_times(policy, P, comments, latency=latency) == (
        last + latency,
        last + latency,
        None,
    )


def test_tied_rows_at_page_cap_are_not_admitted(tmp_path):
    policy = small_policy(tmp_path, page_size=2, page_cap=2)
    tie = P + timedelta(minutes=10)
    comments = [tie, tie, P + timedelta(minutes=20), P + timedelta(minutes=30), P + 1.2 * HOUR]
    first_poll = datetime(2030, 1, 1, 6, tzinfo=UTC)
    # The cap falls inside the tie; which tied row was returned is unknowable.
    assert replay_times(policy, P, comments, latency=timedelta(0)) == (
        None,
        None,
        first_poll,
        first_poll,
        first_poll,
    )


def test_replay_inputs_are_validated(policy):
    with pytest.raises(ValueError):
        replay_times(policy, P, [P - HOUR], latency=timedelta(0))
    with pytest.raises(ValueError):
        replay_times(policy, P, [P], latency=timedelta(minutes=-1))
    with pytest.raises(ValueError):
        replay_times(policy, P, [P.replace(tzinfo=None)], latency=timedelta(0))
    assert replay_times(policy, P, [], latency=timedelta(0)) == ()
    with pytest.raises(ValueError):
        poll_jobs(object(), P, discovered_at=P)


class SyntheticVideo:
    """A provider that lists threads newest first, page by page, as of a moment."""

    def __init__(self, threads, page_size):
        self.threads = sorted(threads, key=lambda thread: thread[1], reverse=True)
        self.page_size = page_size

    def page(self, now, token):
        visible = [thread for thread in self.threads if thread[1] <= now]
        start = token * self.page_size
        rows = visible[start : start + self.page_size]
        more = start + self.page_size < len(visible)
        return rows, token + 1 if more else None


def live_collection(policy, video, poll_times, latency):
    """An independent collector: page until the last-seen thread or the page cap."""
    observed, last_seen = {}, None
    for poll in poll_times:
        token, pages, newest = 0, 0, None
        while token is not None and pages < policy.page_cap:
            rows, token = video.page(poll, token)
            pages += 1
            stop = False
            for thread_id, _ in rows:
                if thread_id == last_seen:
                    stop = True
                    break
                newest = newest or thread_id
                observed.setdefault(thread_id, poll + latency)
            if stop:
                break
        last_seen = newest or last_seen
    return observed


@pytest.mark.parametrize("seed", range(5))
def test_replay_matches_live_visibility_on_synthetic_complete_history(tmp_path, seed):
    policy = small_policy(tmp_path, page_size=3, page_cap=2)
    generator = random.Random(seed)
    # Distinct seconds: a heavy first day, then a long tail past the last poll age.
    seconds = generator.sample(range(1, 86_400), 120) + generator.sample(
        range(86_400, 35 * 86_400), 80
    )
    threads = [(f"t{index}", P + timedelta(seconds=s)) for index, s in enumerate(seconds)]
    latency = timedelta(minutes=7)
    video = SyntheticVideo(threads, policy.page_size)
    observed = live_collection(policy, video, nominal_poll_times(policy, P), latency)
    replayed = replay_times(policy, P, [published for _, published in threads], latency=latency)
    assert replayed == tuple(observed.get(thread_id) for thread_id, _ in threads)
    assert 0 < sum(value is None for value in replayed) < len(threads)
