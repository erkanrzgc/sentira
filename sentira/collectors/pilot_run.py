"""End-to-end synthetic pilot run under a verified lock (BACKTEST B, Phase 1 step 3).

A deterministic synthetic provider stands in for the platform. The run starts at
the registered collection start, discovers the sampled channels' new videos at
the registered ticks, polls them on the schedule of policy P, retrieves the
history span within the retrieval reservation, and stops cleanly at the pilot's
quota ceiling. Every call goes through the metered client, so the ledger is
debited first. Every figure it reports is simulated, never measured.
"""

import heapq
import random
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass, replace
from datetime import timedelta
from fractions import Fraction

from sentira.backtest.pilot import LockedPilot
from sentira.collectors.cost import project, retrieval_units
from sentira.collectors.policy import discovery_time, poll_jobs
from sentira.collectors.quota import MeteredClient
from sentira.config.volume import VolumeAssumptions, exact_share
from sentira.core.document import utc
from sentira.core.registration import integer
from sentira.storage.quota import QuotaExhausted, QuotaLedger

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
# Retrieval runs once a day, shortly after the quota day and the first tick begin.
RETRIEVAL_OFFSET = timedelta(minutes=30)
# Videos older than the history span let a playlist walk see where the span ends.
LEAD_DAYS = 7
# Threads after the last poll age arrive within this window in the synthetic world.
TAIL_HOURS = 720
DISCOVER, POLL, RETRIEVE = 0, 1, 2


class SimulationClock:
    """A clock the run advances; it never moves backwards."""

    def __init__(self, now):
        self.now = utc(now)

    def __call__(self):
        return self.now

    def advance(self, moment):
        moment = utc(moment)
        if moment < self.now:
            raise ValueError("Simulation time cannot move backwards")
        self.now = moment


class SyntheticProvider:
    """Deterministic channels, videos and threads, listed newest first as of the clock."""

    def __init__(self, locked, volume, *, seed, clock):
        if type(locked) is not LockedPilot or type(volume) is not VolumeAssumptions:
            raise ValueError("A verified pilot lock and volume assumptions are required")
        if len(volume.cumulative_share_by_age) != len(locked.policy.poll_ages_hours):
            raise ValueError("One cumulative share is required per poll age")
        self._seed = integer(seed, 0, 2**63 - 1)
        self._clock = clock
        self._volume = volume
        self._policy = locked.policy
        pilot = locked.pilot
        first = pilot.collection_start - (pilot.history_days + LEAD_DAYS) * DAY
        days = LEAD_DAYS + pilot.history_days + pilot.live_days
        self.published_at = {}
        self.log = []
        self._videos = {}
        for _, channels in locked.sample:
            for channel in channels:
                self._videos[channel] = self._generate_videos(channel, first, days)
        self._threads = {}

    def _generate_videos(self, channel, first, days):
        generator = random.Random(f"{self._seed}:{channel}")
        per_day = self._volume.videos_per_channel_day
        rows = []
        for day in range(days):
            for slot in range(per_day):
                offset = (slot + generator.random()) * 86_400 / per_day
                published = first + day * DAY + timedelta(seconds=offset)
                video = f"{channel}-v{len(rows):05d}"
                rows.append((video, published))
                self.published_at[video] = published
        return [row[1] for row in rows], rows

    def _generate_threads(self, video):
        generator = random.Random(f"{self._seed}:{video}")
        draw, threads = generator.random(), 0
        cumulative = Fraction(0)
        for weight, count in self._volume.thread_strata:
            cumulative += exact_share(weight)
            threads = count
            if draw < cumulative:
                break
        ages = self._policy.poll_ages_hours
        shares = self._volume.cumulative_share_by_age
        published = self.published_at[video]
        times = []
        for _ in range(threads):
            point, lower = generator.random(), 0
            for age, share in zip(ages, shares, strict=True):
                if point < share:
                    hours = generator.uniform(lower, age)
                    break
                lower = age
            else:
                hours = generator.uniform(lower, lower + TAIL_HOURS)
            times.append(published + timedelta(hours=hours))
        times.sort()
        rows = [(f"{video}-t{index:05d}", moment) for index, moment in enumerate(times)]
        return times, rows

    def __call__(self, endpoint, params):
        if endpoint == "playlistItems.list":
            times, rows = self._videos[params["channel"]]
            size = self._volume.playlist_page_size
        elif endpoint == "commentThreads.list":
            video = params["video"]
            if video not in self._threads:
                self._threads[video] = self._generate_threads(video)
            times, rows = self._threads[video]
            size = self._policy.page_size
        else:
            raise ValueError("The synthetic provider serves only the registered list methods")
        now = self._clock()
        self.log.append((endpoint, dict(params), now))
        page = params["page"]
        high = bisect_right(times, now) - page * size
        low = max(0, high - size)
        items = [rows[index] for index in range(high - 1, low - 1, -1)]
        return {"items": items, "next": page + 1 if low > 0 else None}


class ProviderError(Exception):
    """A provider call failed; its units stay spent and the run carries on."""


class PilotCeilingReached(Exception):  # noqa: N818 - the name states the condition
    """The next call would take the pilot past its registered quota ceiling."""


class PilotBudget:
    """The pilot's hard ceiling across days, on top of the ledger's daily reservations."""

    def __init__(self, client, quota, ceiling):
        self._client, self._quota, self._ceiling = client, quota, ceiling
        self.spent = 0

    def call(self, purpose, endpoint, params):
        cost = self._quota.cost(endpoint)
        if self.spent + cost > self._ceiling:
            raise PilotCeilingReached("The pilot ceiling is reached")
        try:
            result = self._client.call(purpose, endpoint, params)
        except QuotaExhausted:
            raise
        except BaseException:
            # The ledger debited the call before it failed; the units are spent.
            self.spent += cost
            raise
        self.spent += cost
        return result


@dataclass(frozen=True, slots=True)
class PilotRun:
    locked: LockedPilot
    seed: int
    stopped: str | None
    spent: int
    units: dict
    calls: dict
    live_videos: int
    live_threads_observed: int
    polls_executed: int
    polls_beyond_window: int
    live_refused: int
    failed_calls: int
    history_videos: int
    history_threads: int
    retrieval_complete: bool
    projected_live_units: int
    projected_retrieval_units: int


def _list_new(budget, endpoint, key, params, last_seen, *, limit=None, since=None):
    """Page newest first until the last-seen item, an item before `since`, the end
    of the listing or the page limit."""
    page, newest, items = 0, None, []
    while limit is None or page < limit:
        result = budget.call("live", endpoint, {**params, "page": page, "purpose": "live"})
        for item_id, published in result["items"]:
            newest = newest or item_id
            if item_id == last_seen.get(key) or (since is not None and published < since):
                return items, newest
            items.append((item_id, published))
        if result["next"] is None:
            break
        page += 1
    return items, newest


def run_pilot(locked, provider, ledger, clock):
    """Run a locked pilot against a synthetic provider and return the simulated outcome."""
    if type(locked) is not LockedPilot:
        raise ValueError("A verified pilot lock is required")
    if type(ledger) is not QuotaLedger or ledger.policy != locked.quota:
        raise ValueError("The ledger must run under the locked quota policy")
    if type(clock) is not SimulationClock:
        raise ValueError("A simulation clock is required")
    pilot, policy = locked.pilot, locked.policy
    start = pilot.collection_start
    if clock() > start:
        raise ValueError("A pilot run begins at its registered collection start")
    clock.advance(start)
    end = start + pilot.live_days * DAY
    history_start = start - pilot.history_days * DAY
    budget = PilotBudget(MeteredClient(provider, ledger), locked.quota, pilot.quota_ceiling_units)
    channels = [channel for _, ids in locked.sample for channel in ids]

    events, counter = [], 0

    def schedule(moment, kind, payload):
        nonlocal counter
        heapq.heappush(events, (moment, kind, counter, payload))
        counter += 1

    tick = discovery_time(policy, start)
    while tick < end:
        schedule(tick, DISCOVER, None)
        tick += policy.discovery_interval_hours * HOUR
    for day in range(pilot.live_days):
        schedule(start + day * DAY + RETRIEVAL_OFFSET, RETRIEVE, None)

    seen_video, seen_thread, live_videos = {}, {}, set()
    observed = polls = beyond = refused = failed = history_videos = history_threads = 0
    queue, stopped = None, None
    try:
        while events:
            moment, kind, _, payload = heapq.heappop(events)
            clock.advance(moment)
            if kind == DISCOVER:
                for channel in channels:
                    try:
                        found, newest = _list_new(
                            budget,
                            "playlistItems.list",
                            channel,
                            {"channel": channel},
                            seen_video,
                            since=start,
                        )
                    except QuotaExhausted:
                        refused += 1
                        continue
                    except ProviderError:
                        failed += 1
                        continue
                    if newest is not None:
                        seen_video[channel] = newest
                    # Videos from before collection start belong to retrieval.
                    for video, published in found:
                        if video in live_videos:
                            continue
                        live_videos.add(video)
                        for job in poll_jobs(policy, published, discovered_at=moment):
                            if job.due_at < end:
                                schedule(job.due_at, POLL, video)
                            else:
                                beyond += 1
            elif kind == POLL:
                try:
                    found, newest = _list_new(
                        budget,
                        "commentThreads.list",
                        payload,
                        {"video": payload},
                        seen_thread,
                        limit=policy.page_cap,
                    )
                except QuotaExhausted:
                    refused += 1
                    continue
                except ProviderError:
                    failed += 1
                    continue
                if newest is not None:
                    seen_thread[payload] = newest
                observed += len(found)
                polls += 1
            else:
                if queue is None:
                    queue = deque(("playlistItems.list", channel, 0) for channel in channels)
                while queue:
                    endpoint, key, page = queue[0]
                    field = "channel" if endpoint == "playlistItems.list" else "video"
                    params = {field: key, "page": page, "purpose": "retrieval"}
                    try:
                        result = budget.call("retrieval", endpoint, params)
                    except QuotaExhausted:
                        break
                    except ProviderError:
                        # A failed retrieval page is not retried; it is counted.
                        queue.popleft()
                        failed += 1
                        continue
                    queue.popleft()
                    more = result["next"] is not None
                    if endpoint == "playlistItems.list":
                        for video, published in result["items"]:
                            if published < history_start:
                                more = False
                                break
                            if published < start:
                                queue.append(("commentThreads.list", video, 0))
                                history_videos += 1
                    else:
                        history_threads += len(result["items"])
                    if more:
                        queue.appendleft((endpoint, key, page + 1))
    except PilotCeilingReached:
        stopped = "pilot_ceiling"

    units, calls = {}, {}
    for debit in ledger.debits():
        units[debit.purpose] = units.get(debit.purpose, 0) + debit.units
        label = f"{debit.endpoint}:{debit.purpose}"
        calls[label] = calls.get(label, 0) + 1
    sampled = replace(locked.volume, channels=pilot.total_channels)
    return PilotRun(
        locked=locked,
        seed=provider._seed,
        stopped=stopped,
        spent=budget.spent,
        units=units,
        calls=calls,
        live_videos=len(live_videos),
        live_threads_observed=observed,
        polls_executed=polls,
        polls_beyond_window=beyond,
        live_refused=refused,
        failed_calls=failed,
        history_videos=history_videos,
        history_threads=history_threads,
        retrieval_complete=queue is not None and not queue,
        projected_live_units=project(policy, locked.quota, sampled).live_units * pilot.live_days,
        projected_retrieval_units=retrieval_units(
            policy, locked.quota, sampled, pilot.history_days
        ),
    )


def render_run(result):
    """Deterministic Markdown for a simulated pilot run."""
    if type(result) is not PilotRun:
        raise ValueError("A pilot run is required")
    pilot = result.locked.pilot
    outcome = "stopped at the pilot ceiling" if result.stopped else "completed its live window"
    lines = [
        "# Synthetic pilot run",
        "",
        "Every figure below is *simulated*: a deterministic synthetic provider stood in for "
        "the platform and no platform was contacted. Simulated figures test the machinery, "
        "not the world.",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Outcome | {outcome} |",
        f"| Units spent | {result.spent:,} of a ceiling of {pilot.quota_ceiling_units:,} |",
        f"| Live videos discovered | {result.live_videos:,} |",
        f"| Live polls executed | {result.polls_executed:,}; "
        f"{result.polls_beyond_window:,} fell due after the live window |",
        f"| Live calls refused by the daily reservation | {result.live_refused:,} |",
        f"| Failed provider calls, units spent | {result.failed_calls:,} |",
        f"| Threads observed live | {result.live_threads_observed:,} |",
        f"| History videos and threads retrieved | {result.history_videos:,} and "
        f"{result.history_threads:,}; retrieval "
        f"{'complete' if result.retrieval_complete else 'incomplete'} |",
        "",
        "## Executed and projected units",
        "",
        "| Purpose | Executed (simulated) | Projected (calculated) |",
        "| --- | ---: | ---: |",
        f"| Live | {result.units.get('live', 0):,} | {result.projected_live_units:,} |",
        f"| Retrieval | {result.units.get('retrieval', 0):,} | "
        f"{result.projected_retrieval_units:,} |",
        "",
        "The projection is a steady state: it counts every poll age of every video and "
        "every thread of a history video. A finite live window leaves later poll ages "
        "unrun, and history videos younger than their thread-arrival window have fewer "
        "threads at retrieval, so the executed figures are lower.",
        "",
        "## Provenance",
        "",
        f"- Pilot `{pilot.version}`, lock digests: "
        + ", ".join(f"`{value}`" for value in result.locked.digests),
        f"- Synthetic provider seed: {result.seed}",
    ]
    return "\n".join(lines) + "\n"
