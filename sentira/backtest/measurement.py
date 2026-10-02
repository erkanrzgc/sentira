"""The measured addendum, computed by registered label-free rules (BACKTEST A.3, A.9).

Only rows published in the pre-origin span [D0, O1) and visible by O1 are read,
through the shared strict visibility rule. Order of computation, as registered:
c_min and k_floor from the hourly volume distribution, then episodes, then the
median excess half-life and hence the horizon H.
"""

import math
from bisect import bisect_left
from statistics import median

from sentira.backtest.registration import Cell, Measured, Registration, horizon_for
from sentira.core.registration import digest
from sentira.series.episodes import HOUR, Rules, detect_with_rules
from sentira.storage.asof import VisibilityCursor

# Scales a median absolute deviation to a normal standard deviation.
MAD_TO_SIGMA = 1.4826


def preorigin_rows(series, registration):
    """Rows visible at O1 and published in [D0, O1), per topic, in publication order."""
    walk = registration.walk_forward
    start, origin = walk.history_start, walk.first_origin
    if series.start != start:
        raise ValueError("The series must start at the registered history start")
    if series.end < origin:
        raise ValueError("The pre-origin span is incomplete; the addendum cannot be locked")
    result = {}
    for topic, rows in sorted(series.topics.items()):
        visible = VisibilityCursor(rows, observed_at=lambda row: row.visible_at).advance(origin)
        kept = [row for row in visible if start <= row.published_at < origin]
        result[topic] = tuple(sorted(kept, key=lambda row: (row.published_at, row.visible_at)))
    return result


def preorigin_digest(rows_by_topic):
    return digest(
        {
            topic: [[row.published_at, row.visible_at] for row in rows]
            for topic, rows in rows_by_topic.items()
        }
    )


def hourly_volumes(rows_by_topic, start, origin):
    """Counts for every topic-hour in [start, origin), zero hours included."""
    hours = int((origin - start) / HOUR)
    volumes = []
    for rows in rows_by_topic.values():
        counts = [0] * hours
        for row in rows:
            counts[int((row.published_at - start) / HOUR)] += 1
        volumes.extend(counts)
    return volumes


def ceiling(value):
    # Rounding first keeps representation noise from moving an exact integer up.
    return math.ceil(round(value, 9))


def half_life(published, episode, origin, *, trailing_hours):
    """Hours from the last peak of the hourly excess rate to half of that peak.

    The series starts with the trailing window that opened the episode, so the
    hours that triggered onset, often the peak itself, are included.
    """
    first = episode.onset_at - trailing_hours * HOUR
    ended = episode.ended_at if episode.ended_at is not None else origin
    buckets = int((ended - first) / HOUR)
    rate = episode.baseline / 24
    excess = []
    for index in range(buckets):
        low = first + index * HOUR
        count = bisect_left(published, low + HOUR) - bisect_left(published, low)
        excess.append(count - rate)
    if not excess or max(excess) <= 0:
        return None
    peak = max(excess)
    last_peak = max(index for index, value in enumerate(excess) if value == peak)
    for index in range(last_peak + 1, buckets):
        if excess[index] <= peak / 2:
            return index - last_peak
    return None


def select_horizon(lives, surge):
    """H from the median half-life, or the largest horizon with too few half-lives."""
    if len(lives) < surge.measurement.minimum_half_life_episodes:
        return None, horizon_for(None, surge)
    half = float(median(lives))
    return half, horizon_for(half, surge)


def measure(series, registration):
    """Compute the measured addendum from the pre-origin span of a synthetic series."""
    if type(registration) is not Registration:
        raise ValueError("A validated registration is required")
    surge, rules = registration.surge, registration.surge.measurement
    walk = registration.walk_forward
    start, origin = walk.history_start, walk.first_origin
    rows = preorigin_rows(series, registration)

    volumes = hourly_volumes(rows, start, origin)
    centre = float(median(volumes)) if volumes else 0.0
    spread = float(median(abs(value - centre) for value in volumes)) if volumes else 0.0
    sigma = MAD_TO_SIGMA * spread
    window = surge.trailing_hours
    c_min = max(
        rules.minimum_c_min, ceiling(window * centre + rules.c_min_z * math.sqrt(window) * sigma)
    )
    k_floor = max(rules.minimum_k_floor, ceiling(rules.k_floor_z * math.sqrt(window) * sigma))

    # The largest registered horizon keeps the maximum duration from cutting decay short.
    cell = Cell(
        surge.primary_onset_multiplier, surge.primary_size_multiplier, max(surge.horizons_hours)
    )
    detection = Rules.with_thresholds(registration, c_min, k_floor)
    lives = []
    for topic_rows in rows.values():
        found = detect_with_rules(topic_rows, detection, (cell,), start=start, end=origin)[cell]
        published = [row.published_at for row in topic_rows]
        lives.extend(
            value
            for value in (
                half_life(published, episode, origin, trailing_hours=surge.trailing_hours)
                for episode in found
            )
            if value is not None
        )
    half, horizon = select_horizon(lives, surge)

    sha256 = preorigin_digest(rows)
    return Measured(
        mode="synthetic",
        version=f"measured-{sha256[:12]}",
        registration_version=registration.version,
        preorigin_sha256=sha256,
        hourly_median=centre,
        hourly_mad=spread,
        c_min=c_min,
        k_floor=k_floor,
        half_life_episodes=len(lives),
        half_life_hours=half,
        horizon_hours=horizon,
    )


def render_measured(measured):
    """Deterministic TOML for a measured addendum."""
    lines = [
        "# Computed by `python -m sentira.cli measure` from the pre-origin span.",
        "# Do not edit: counting recomputes these values and refuses any difference.",
        f'mode = "{measured.mode}"',
        f'version = "{measured.version}"',
        f'registration_version = "{measured.registration_version}"',
        f'preorigin_sha256 = "{measured.preorigin_sha256}"',
        f"hourly_median = {measured.hourly_median!r}",
        f"hourly_mad = {measured.hourly_mad!r}",
        f"c_min = {measured.c_min}",
        f"k_floor = {measured.k_floor}",
        f"half_life_episodes = {measured.half_life_episodes}",
    ]
    if measured.half_life_hours is not None:
        lines.append(f"half_life_hours = {measured.half_life_hours!r}")
    lines.append(f"horizon_hours = {measured.horizon_hours}")
    return "\n".join(lines) + "\n"
