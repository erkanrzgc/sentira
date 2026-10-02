"""Surge episodes on a strict as-of series (BACKTEST A.2 and A.3); synthetic input only.

At each hourly tick only rows visible by that tick are read. Episodes therefore
never depend on rows that become visible later, and nothing is back-dated.
"""

from bisect import bisect_left, bisect_right, insort
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import median

from sentira.backtest.registration import Cell, LockedRegistration
from sentira.core.document import utc

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Observation:
    published_at: datetime
    visible_at: datetime

    def __post_init__(self):
        published, visible = utc(self.published_at), utc(self.visible_at)
        if visible < published:
            raise ValueError("A row cannot be visible before publication")
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "visible_at", visible)


@dataclass(frozen=True, slots=True)
class Episode:
    onset_at: datetime
    baseline: float
    k: float
    k_floor_binds: bool
    tau_k: datetime | None
    overshoot: float | None
    detected_at_crossing: bool
    crossed_2k_at: datetime | None
    resolves_at: datetime | None
    label: str
    ended_at: datetime | None
    end_reason: str

    @property
    def in_t1_population(self):
        return self.label in ("positive", "negative") and not self.detected_at_crossing


@dataclass(slots=True)
class _Open:
    onset_at: datetime
    baseline: float
    k: float
    k_floor_binds: bool
    tau_k: datetime | None = None
    overshoot: float | None = None
    detected_at_crossing: bool = False
    crossed_2k_at: datetime | None = None
    quiet_hours: int = 0


def whole_hour(value):
    value = utc(value)
    if value.minute or value.second or value.microsecond:
        raise ValueError("Evaluation bounds must fall on whole hours")
    return value


class _AsOfSeries:
    """Rows visible so far, indexed by publication time and local calendar day."""

    def __init__(self, observations, offset):
        if any(type(row) is not Observation for row in observations):
            raise ValueError("Validated observations are required")
        self._pending = sorted(observations, key=lambda row: row.visible_at)
        self._cursor = 0
        self._offset = offset
        self.published = []
        self.daily = Counter()
        # Set when a newly visible row belongs to a day before the current tick's day.
        self.past_changed = False

    def local_date(self, moment) -> date:
        return (moment + self._offset).date()

    def advance(self, tick):
        today = self.local_date(tick)
        while self._cursor < len(self._pending):
            row = self._pending[self._cursor]
            if row.visible_at > tick:
                break
            insort(self.published, row.published_at)
            day = self.local_date(row.published_at)
            self.daily[day] += 1
            self.past_changed |= day < today
            self._cursor += 1

    def count_since(self, moment):
        # Every visible row was published at or before the current tick.
        return len(self.published) - bisect_left(self.published, moment)

    def trailing(self, tick, window):
        # Rows published in (tick - window, tick].
        return len(self.published) - bisect_right(self.published, tick - window)


def detect_episodes(observations, locked, cell, *, start, end):
    """Return the episodes of one topic series for one registered grid cell."""
    if type(locked) is not LockedRegistration:
        raise ValueError("A locked registration is required")
    if type(cell) is not Cell or cell not in locked.grid:
        raise ValueError("The cell is not in the registered grid")
    start, end = whole_hour(start), whole_hour(end)
    if end <= start:
        raise ValueError("The evaluation span must be positive")
    surge = locked.registration.surge
    measured = locked.measured
    offset = timedelta(minutes=locked.registration.calendar_utc_offset_minutes)
    series = _AsOfSeries(tuple(observations), offset)

    # Baselines use whole local days inside the data only (the burn-in).
    first_local = start + offset
    first_day = first_local.date()
    if first_local.time() != time(0):
        first_day += DAY
    trailing = timedelta(hours=surge.trailing_hours)
    horizon = timedelta(hours=cell.horizon_hours)
    max_duration = horizon * surge.max_duration_horizons
    refractory = timedelta(hours=surge.refractory_hours)

    cached = {}

    def baseline_at(tick):
        # Past daily counts change only with a new day or a late row for a past day.
        today = series.local_date(tick)
        if series.past_changed or cached.get("day") != today:
            days = [today - DAY * i for i in range(1, surge.baseline_days + 1)]
            value = None
            if days[-1] >= first_day:
                value = float(median(series.daily[day] for day in days))
            cached.update(day=today, value=value)
            series.past_changed = False
        return cached["value"]

    def close(state, ended_at, reason):
        if state.tau_k is None:
            resolves_at, label = None, "below_k"
        else:
            resolves_at = state.tau_k + horizon
            if resolves_at > end:
                label = "censored"
            else:
                label = "positive" if state.crossed_2k_at is not None else "negative"
        return Episode(
            onset_at=state.onset_at,
            baseline=state.baseline,
            k=state.k,
            k_floor_binds=state.k_floor_binds,
            tau_k=state.tau_k,
            overshoot=state.overshoot,
            detected_at_crossing=state.detected_at_crossing,
            crossed_2k_at=state.crossed_2k_at,
            resolves_at=resolves_at,
            label=label,
            ended_at=ended_at,
            end_reason=reason,
        )

    episodes = []
    current = None
    last_end = None
    tick = start
    while tick < end:
        tick += HOUR
        series.advance(tick)
        count = series.trailing(tick, trailing)
        baseline = baseline_at(tick)
        if baseline is None:
            continue
        if current is None:
            if last_end is not None and tick - last_end < refractory:
                continue
            if count >= cell.onset_multiplier * baseline and count >= measured.c_min:
                scaled = cell.size_multiplier * baseline
                current = _Open(
                    tick, baseline, max(scaled, measured.k_floor), scaled < measured.k_floor
                )
            continue
        size = series.count_since(current.onset_at) - current.baseline * (
            (tick - current.onset_at) / DAY
        )
        if current.tau_k is None:
            if size >= current.k:
                current.tau_k = tick
                current.overshoot = size / current.k
                current.detected_at_crossing = size >= 2 * current.k
        elif (
            current.crossed_2k_at is None
            and tick <= current.tau_k + horizon
            and size >= 2 * current.k
        ):
            current.crossed_2k_at = tick
        # The end rule uses the current rolling baseline, not the frozen one.
        current.quiet_hours = current.quiet_hours + 1 if count < baseline else 0
        if current.quiet_hours >= surge.end_quiet_hours:
            episodes.append(close(current, tick, "quiet"))
        elif tick - current.onset_at >= max_duration:
            episodes.append(close(current, tick, "max_duration"))
        else:
            continue
        current, last_end = None, tick
    if current is not None:
        episodes.append(close(current, None, "open"))
    return tuple(episodes)
