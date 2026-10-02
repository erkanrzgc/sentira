"""Calculated quota cost of policy P from assumed volumes (BACKTEST B, D.2).

Live polls are costed on the registered schedule itself: the poll jobs of a video
are averaged over every publication minute of one discovery interval, so
coalescing at discovery is counted exactly as the collector would run it. Each
thread stratum is costed separately, because page counts and the page cap are
not linear in the number of threads. Every figure is calculated; none is measured.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction

from sentira.collectors.policy import discovery_time, poll_jobs
from sentira.config.collection import CollectionPolicy
from sentira.config.quota import QuotaPolicy
from sentira.config.volume import VolumeAssumptions, exact_share

DISCOVERY_ENDPOINT = "playlistItems.list"
THREADS_ENDPOINT = "commentThreads.list"
DAYS_PER_YEAR = 365
# Any midnight serves: discovery ticks repeat every interval from midnight UTC.
ANCHOR = datetime(2030, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Projection:
    policy: CollectionPolicy
    quota: QuotaPolicy
    volume: VolumeAssumptions
    videos_per_day: int
    discovery_units: int
    poll_pages_per_video: Fraction
    poll_units: int
    live_units: int
    lost_threads_per_day: int
    unpolled_threads_per_day: int
    retrieval_units_per_history_year: int
    retrieval_days_per_history_year: int | None
    reachable_history_days: int | None


def ceil_divide(numerator, denominator):
    """Exact ceiling of a quotient of integers or fractions, without floats."""
    return -(-numerator // denominator)


def _listing_pages(items, page_size):
    # A listing call returns a page even when it holds nothing.
    return max(1, ceil_divide(items, page_size))


def _poll_pages(new, page_size, cap, *, first):
    """Pages one poll spends on `new` threads, within the page cap.

    The first poll of a video stops when the listing ends. A later poll stops on
    reaching the newest thread already seen, which it finds only on the page that
    holds it, so it reads one page past its whole pages of new threads.
    """
    pages = _listing_pages(new, page_size) if first else new // page_size + 1
    return min(cap, pages)


def _schedules(policy):
    """For every publication minute of one discovery interval, each job's last age."""
    minutes = policy.discovery_interval_hours * 60
    schedules = []
    for minute in range(minutes):
        published = ANCHOR + timedelta(minutes=minute)
        jobs = poll_jobs(policy, published, discovered_at=discovery_time(policy, published))
        schedules.append([job.ages_hours[-1] for job in jobs])
    return schedules


def _poll_cost(policy, schedules, shares, threads):
    """Average pages and lost threads per video with `threads` threads."""
    limit = policy.per_poll_limit
    pages = lost = Fraction(0)
    for ages in schedules:
        seen = Fraction(0)
        for index, age in enumerate(ages):
            # Shares are registered at poll ages; a coalesced job reaches its last age.
            new = (shares[age] - seen) * threads
            seen = shares[age]
            pages += _poll_pages(new, policy.page_size, policy.page_cap, first=index == 0)
            lost += max(Fraction(0), new - limit)
    return pages / len(schedules), lost / len(schedules)


def retrieval_units(policy, quota, volume, days):
    """Calculated units to retrieve `days` days of history for every channel.

    Every thread of every video is read, at least one page per video, and each
    channel's upload playlist is enumerated over the span, at least one page.
    """
    listing, threads_cost = quota.cost(DISCOVERY_ENDPOINT), quota.cost(THREADS_ENDPOINT)
    pages_per_video = sum(
        exact_share(weight) * _listing_pages(threads, policy.page_size)
        for weight, threads in volume.thread_strata
    )
    per_channel = volume.videos_per_channel_day * days
    units = math.ceil(volume.channels * per_channel * pages_per_video * threads_cost)
    return (
        units + volume.channels * _listing_pages(per_channel, volume.playlist_page_size) * listing
    )


def project(policy, quota, volume):
    if (
        type(policy) is not CollectionPolicy
        or type(quota) is not QuotaPolicy
        or type(volume) is not VolumeAssumptions
    ):
        raise ValueError("Validated policy, quota and volume inputs are required")
    if len(volume.cumulative_share_by_age) != len(policy.poll_ages_hours):
        raise ValueError("One cumulative share is required per poll age")
    listing, threads_cost = quota.cost(DISCOVERY_ENDPOINT), quota.cost(THREADS_ENDPOINT)
    videos_per_day = volume.channels * volume.videos_per_channel_day
    shares = {
        age: exact_share(value)
        for age, value in zip(policy.poll_ages_hours, volume.cumulative_share_by_age, strict=True)
    }
    never_polled = 1 - shares[policy.poll_ages_hours[-1]]

    ticks = 24 // policy.discovery_interval_hours
    per_tick = Fraction(volume.videos_per_channel_day, ticks)
    discovery = (
        volume.channels * ticks * _listing_pages(per_tick, volume.playlist_page_size) * listing
    )

    schedules = _schedules(policy)
    pages_per_video = lost_per_video = unpolled_per_video = Fraction(0)
    for weight, threads in volume.thread_strata:
        weight = exact_share(weight)
        pages, lost = _poll_cost(policy, schedules, shares, threads)
        pages_per_video += weight * pages
        lost_per_video += weight * lost
        unpolled_per_video += weight * never_polled * threads
    polls = math.ceil(videos_per_day * pages_per_video * threads_cost)

    retrieval = retrieval_units(policy, quota, volume, DAYS_PER_YEAR)
    reserved = quota.reservation("retrieval")
    per_day = volume.videos_per_channel_day

    return Projection(
        policy=policy,
        quota=quota,
        volume=volume,
        videos_per_day=videos_per_day,
        discovery_units=discovery,
        poll_pages_per_video=pages_per_video,
        poll_units=polls,
        live_units=discovery + polls,
        lost_threads_per_day=math.ceil(videos_per_day * lost_per_video),
        unpolled_threads_per_day=math.ceil(videos_per_day * unpolled_per_video),
        retrieval_units_per_history_year=retrieval,
        retrieval_days_per_history_year=ceil_divide(retrieval, reserved) if reserved else None,
        reachable_history_days=volume.playlist_item_ceiling // per_day if per_day else None,
    )


def _number(value):
    if isinstance(value, Fraction) and value.denominator != 1:
        return f"{float(value):,.2f}"
    return f"{int(value):,}"


def _percent(value):
    return f"{float(exact_share(value) * 100):g}%"


def render_cost(result):
    """Deterministic Markdown for a cost projection."""
    if type(result) is not Projection:
        raise ValueError("A cost projection is required")
    policy, quota, volume = result.policy, result.quota, result.volume
    ages = ", ".join(str(age) for age in policy.poll_ages_hours)
    shares = ", ".join(str(value) for value in volume.cumulative_share_by_age)
    live_reservation = quota.reservation("live")
    spare = live_reservation - result.live_units
    if spare >= 0:
        live_result = f"within the live reservation ({spare:,} units spare)"
    else:
        live_result = f"**exceeds the live reservation by {-spare:,} units**"
    if result.retrieval_days_per_history_year is None:
        retrieval_result = "**no retrieval reservation**"
    else:
        days = result.retrieval_days_per_history_year
        retrieval_result = f"{days:,} days of retrieval per history-year"
    lines = [
        "# Quota cost projection (synthetic)",
        "",
        "Every figure below is *calculated* from the collection policy, the quota policy "
        "and assumed volumes; none is measured. No collection was run.",
        "",
        "## Inputs",
        "",
        "| Input | Value |",
        "| --- | --- |",
        f"| Assumed channels | {volume.channels:,} |",
        f"| Assumed videos per channel-day | {volume.videos_per_channel_day:,} |",
        *(
            f"| Assumed thread stratum | {_percent(weight)} of videos at {threads:,} threads |"
            for weight, threads in volume.thread_strata
        ),
        f"| Assumed cumulative thread share at ages {ages} h | {shares} |",
        f"| Registered playlist page size | {volume.playlist_page_size} |",
        f"| Reported playlist item ceiling (unverified) | {volume.playlist_item_ceiling:,} |",
        f"| Policy *P* | discovery every {policy.discovery_interval_hours} h; polls at {ages} h; "
        f"at most {policy.page_cap} pages of {policy.page_size} |",
        "",
        "## Daily units (calculated)",
        "",
        "| Purpose | Units | Reservation | Result |",
        "| --- | ---: | ---: | --- |",
        f"| Live discovery | {result.discovery_units:,} | | |",
        f"| Live polls ({_number(result.poll_pages_per_video)} pages per video, "
        f"{result.videos_per_day:,} videos) | {result.poll_units:,} | | |",
        f"| Live total | {result.live_units:,} | {live_reservation:,} | {live_result} |",
        f"| Historical retrieval | {result.retrieval_units_per_history_year:,} per "
        f"history-year | {quota.reservation('retrieval'):,} | {retrieval_result} |",
        f"| Survival | not projected | {quota.reservation('survival'):,} | strata design pending |",
        f"| Buffer | not counted | {quota.reservation('buffer'):,} | |",
        "",
        "## Coverage (calculated)",
        "",
        f"- Threads beyond the page cap: {result.lost_threads_per_day:,} per day.",
        f"- Threads published after the last poll age, never observed live: "
        f"{result.unpolled_threads_per_day:,} per day.",
    ]
    reachable = result.reachable_history_days
    if reachable is None:
        lines.append("- No videos are assumed, so the playlist ceiling does not bind.")
    else:
        lines.append(
            f"- History reachable per channel at the reported playlist ceiling: {reachable:,} days."
        )
        if reachable < DAYS_PER_YEAR:
            lines.append(
                "- **A history-year exceeds the reported playlist ceiling at this volume; "
                "retrieval beyond it may be impossible.**"
            )
    lines += [
        "",
        "## Provenance",
        "",
        f"- Collection policy `{policy.version}`: `{policy.sha256}`",
        f"- Quota policy `{quota.version}`: `{quota.sha256}`",
        f"- Volume assumptions `{volume.version}`: `{volume.sha256}`",
    ]
    return "\n".join(lines) + "\n"
