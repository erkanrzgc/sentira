"""Polling schedule and replay visibility under the registered policy P (BACKTEST 0.3).

Discovery precedes polling. At discovery, or at a restart, every age already due
is coalesced into one immediate poll; later ages stay anchored to publication.
Replay applies the same schedule, from on-time discovery, to a retrieved video:
a thread is replay-visible at the poll that would have returned it, plus the job
latency, and never where no poll would have reached it.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sentira.config.collection import CollectionPolicy
from sentira.core.document import utc

HOUR = timedelta(hours=1)


def _policy(value):
    if type(value) is not CollectionPolicy:
        raise ValueError("A validated collection policy is required")
    return value


def discovery_time(policy, published_at):
    """The first registered discovery tick at or after publication."""
    interval = _policy(policy).discovery_interval_hours * HOUR
    published = utc(published_at)
    midnight = datetime.combine(published.date(), datetime.min.time(), tzinfo=UTC)
    ticks = -(-(published - midnight) // interval)
    try:
        return midnight + ticks * interval
    except OverflowError:
        raise ValueError("The discovery time cannot be represented") from None


@dataclass(frozen=True, slots=True)
class PollJob:
    published_at: datetime
    ages_hours: tuple[int, ...]
    due_at: datetime
    # A catch-up after the last registered age is a live observation only.
    live_only: bool

    @property
    def missed_ages_hours(self):
        """Covered ages whose registered time passed before the job was due."""
        return tuple(age for age in self.ages_hours if self.published_at + age * HOUR < self.due_at)


def poll_jobs(policy, published_at, *, discovered_at, completed=(), resumed_at=None):
    """The remaining poll jobs for one video, from discovery or from a restart."""
    ages = _policy(policy).poll_ages_hours
    published, start = utc(published_at), utc(discovered_at)
    if start < published:
        raise ValueError("A video cannot be discovered before publication")
    if resumed_at is not None:
        start = max(start, utc(resumed_at))
    try:
        nominal = {age: published + age * HOUR for age in ages}
    except OverflowError:
        raise ValueError("Poll times cannot be represented") from None
    done = tuple(completed)
    if any(type(age) is not int or age not in nominal for age in done):
        raise ValueError("Completed ages must be registered poll ages")
    if any(nominal[age] > start for age in done):
        raise ValueError("An age cannot be completed before it is due")
    pending = [age for age in ages if age not in done]
    due = tuple(age for age in pending if nominal[age] <= start)
    jobs = []
    if due:
        jobs.append(PollJob(published, due, start, live_only=start > nominal[ages[-1]]))
    jobs.extend(
        PollJob(published, (age,), nominal[age], live_only=False)
        for age in pending
        if nominal[age] > start
    )
    return tuple(jobs)


def nominal_poll_times(policy, published_at):
    """Poll times under P with discovery at the first registered tick.

    A catch-up after the last registered age is a live observation only, so it
    is never a replay poll; it can arise where discovery is slower than the ages.
    """
    jobs = poll_jobs(policy, published_at, discovered_at=discovery_time(policy, published_at))
    return tuple(job.due_at for job in jobs if not job.live_only)


def replay_times(policy, video_published_at, comments_published, *, latency):
    """Replay time of each thread on a video, or None where no poll would return it.

    Each poll lists threads newest first and stops at the newest thread already
    seen or after the page cap. Threads behind the cap are therefore never
    returned later. Where the cap falls inside a group of equal publication
    times, the provider's order within the group is unknown and none of the
    group is admitted at that poll. Supply every thread on the video: replay on
    survivors alone can admit threads that were originally behind the cap.
    """
    policy = _policy(policy)
    if type(latency) is not timedelta or latency < timedelta(0):
        raise ValueError("A non-negative job latency is required")
    video = utc(video_published_at)
    times = [utc(value) for value in comments_published]
    if any(value < video for value in times):
        raise ValueError("A thread cannot precede its video")
    order = sorted(range(len(times)), key=lambda index: times[index])
    ordered = [times[index] for index in order]
    result = [None] * len(times)
    limit = policy.per_poll_limit
    newest_seen = None
    for poll in nominal_poll_times(policy, video):
        # Unseen threads listable at this poll occupy positions [low, high).
        high = bisect_right(ordered, poll)
        low = 0 if newest_seen is None else bisect_right(ordered, newest_seen)
        if high <= low:
            continue
        returned = range(max(low, high - limit), high)
        if high - low > limit:
            boundary = ordered[high - limit - 1]
            returned = [position for position in returned if ordered[position] != boundary]
        for position in returned:
            result[order[position]] = poll + latency
        newest_seen = ordered[high - 1]
    return tuple(result)
