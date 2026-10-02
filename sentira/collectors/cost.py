"""Calculated quota cost of policy P from assumed volumes (BACKTEST B, D.2).

Live polls are costed on the registered schedule itself: the poll jobs of a video
are averaged over every publication minute of one discovery interval, so
coalescing at discovery is counted exactly as the collector would run it. Every
figure is calculated; none is measured.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction

from sentira.collectors.policy import discovery_time, poll_jobs
from sentira.config.collection import CollectionPolicy
from sentira.config.quota import QuotaPolicy
from sentira.config.volume import VolumeAssumptions

DISCOVERY_ENDPOINT = "playlistItems.list"
THREADS_ENDPOINT = "commentThreads.list"
DAYS_PER_YEAR = 365
# Any midnight serves: discovery ticks repeat every interval from midnight UTC.
ANCHOR = datetime(2030, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Projection:
    policy: CollectionPolicy
    volume: VolumeAssumptions
    policy_sha256: str
    quota_sha256: str
    volume_sha256: str
    videos_per_day: int
    discovery_units: int
    poll_pages_per_video: Fraction
    poll_units: int
    live_units: int
    live_reservation: int
    lost_threads_per_day: int
    retrieval_units_per_history_year: int
    retrieval_reservation: int
    retrieval_days_per_history_year: int | None
    survival_reservation: int
    buffer_reservation: int


def _pages(threads, page_size, cap=None):
    # Every call returns at least one page, even when nothing is new.
    pages = max(1, math.ceil(threads / page_size))
    return pages if cap is None else min(cap, pages)


def _poll_cost(policy, volume):
    """Average pages and lost threads per video over one discovery interval."""
    shares = dict(
        zip(
            policy.poll_ages_hours,
            (Fraction(str(value)) for value in volume.cumulative_share_by_age),
            strict=True,
        )
    )
    limit = policy.per_poll_limit
    minutes = policy.discovery_interval_hours * 60
    pages = lost = Fraction(0)
    for minute in range(minutes):
        published = ANCHOR + timedelta(minutes=minute)
        seen = Fraction(0)
        for job in poll_jobs(policy, published, discovered_at=discovery_time(policy, published)):
            # Shares are registered at poll ages; a coalesced job reaches its last age.
            reached = shares[job.ages_hours[-1]]
            new = (reached - seen) * volume.threads_per_video
            seen = reached
            pages += _pages(new, policy.page_size, policy.page_cap)
            lost += max(Fraction(0), new - limit)
    return pages / minutes, lost / minutes


def project(policy, quota, volume):
    if (
        type(policy) is not CollectionPolicy
        or type(quota) is not QuotaPolicy
        or type(volume) is not VolumeAssumptions
    ):
        raise ValueError("Validated policy, quota and volume inputs are required")
    if len(volume.cumulative_share_by_age) != len(policy.poll_ages_hours):
        raise ValueError("One cumulative share is required per poll age")
    listing, threads = quota.cost(DISCOVERY_ENDPOINT), quota.cost(THREADS_ENDPOINT)
    videos_per_day = volume.channels * volume.videos_per_channel_day

    ticks = 24 // policy.discovery_interval_hours
    per_tick = Fraction(volume.videos_per_channel_day, ticks)
    discovery = volume.channels * ticks * _pages(per_tick, volume.playlist_page_size) * listing

    pages_per_video, lost_per_video = _poll_cost(policy, volume)
    polls = math.ceil(videos_per_day * pages_per_video * threads)
    live = discovery + polls

    # Retrieval pages every thread of every video, then enumerates the playlists.
    videos_per_year = videos_per_day * DAYS_PER_YEAR
    retrieval = videos_per_year * _pages(volume.threads_per_video, policy.page_size) * threads
    channel_year = volume.videos_per_channel_day * DAYS_PER_YEAR
    retrieval += volume.channels * _pages(channel_year, volume.playlist_page_size) * listing
    reserved = quota.reservation("retrieval")

    return Projection(
        policy=policy,
        volume=volume,
        policy_sha256=policy.sha256,
        quota_sha256=quota.sha256,
        volume_sha256=volume.sha256,
        videos_per_day=videos_per_day,
        discovery_units=discovery,
        poll_pages_per_video=pages_per_video,
        poll_units=polls,
        live_units=live,
        live_reservation=quota.reservation("live"),
        lost_threads_per_day=math.ceil(videos_per_day * lost_per_video),
        retrieval_units_per_history_year=retrieval,
        retrieval_reservation=reserved,
        retrieval_days_per_history_year=math.ceil(retrieval / reserved) if reserved else None,
        survival_reservation=quota.reservation("survival"),
        buffer_reservation=quota.reservation("buffer"),
    )


def _number(value):
    if isinstance(value, Fraction) and value.denominator != 1:
        return f"{float(value):,.2f}"
    return f"{int(value):,}"


def render_cost(result):
    """Deterministic Markdown for a cost projection."""
    if type(result) is not Projection:
        raise ValueError("A cost projection is required")
    policy, volume = result.policy, result.volume
    ages = ", ".join(str(age) for age in policy.poll_ages_hours)
    shares = ", ".join(str(value) for value in volume.cumulative_share_by_age)
    spare = result.live_reservation - result.live_units
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
        f"| Assumed threads per video | {volume.threads_per_video:,} |",
        f"| Assumed cumulative thread share at ages {ages} h | {shares} |",
        f"| Registered playlist page size | {volume.playlist_page_size} |",
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
        f"| Live total | {result.live_units:,} | {result.live_reservation:,} | {live_result} |",
        f"| Historical retrieval | {result.retrieval_units_per_history_year:,} per "
        f"history-year | {result.retrieval_reservation:,} | {retrieval_result} |",
        f"| Survival | not projected | {result.survival_reservation:,} | strata design pending |",
        f"| Buffer | not counted | {result.buffer_reservation:,} | |",
        "",
        f"Threads beyond the page cap: {result.lost_threads_per_day:,} per day (calculated).",
        "",
        "## Provenance",
        "",
        f"- Collection policy `{policy.version}`: `{result.policy_sha256}`",
        f"- Quota policy: `{result.quota_sha256}`",
        f"- Volume assumptions `{volume.version}`: `{result.volume_sha256}`",
    ]
    return "\n".join(lines) + "\n"
