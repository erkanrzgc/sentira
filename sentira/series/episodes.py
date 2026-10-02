"""Surge episodes on a strict as-of series (BACKTEST A.2 and A.3); synthetic input only.

At each hourly tick only rows visible by that tick are read, through the shared
strict visibility rule in `storage/asof.py`. Episodes therefore never depend on
rows that become visible later, and nothing is back-dated. One pass over the
ticks serves every requested grid cell.
"""

from bisect import bisect_left, bisect_right, insort
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import median

from sentira.backtest.registration import Cell, LockedRegistration
from sentira.core.document import utc
from sentira.storage.asof import VisibilityCursor

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
    """One episode. Labels: positive, negative, censored, detected_at_crossing,
    below_k (ended before reaching k) or open (data ended before k or an end)."""

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
        return self.label in ("positive", "negative")


@dataclass(frozen=True, slots=True)
class Rules:
    """Cell-independent detection rules taken from a registration and its thresholds."""

    baseline_days: int
    trailing_hours: int
    end_quiet_hours: int
    refractory_hours: int
    max_duration_horizons: int
    calendar_utc_offset_minutes: int
    c_min: int
    k_floor: int

    @classmethod
    def from_locked(cls, locked):
        if type(locked) is not LockedRegistration:
            raise ValueError("A locked registration is required")
        measured = locked.measured
        return cls.with_thresholds(locked.registration, measured.c_min, measured.k_floor)

    @classmethod
    def with_thresholds(cls, registration, c_min, k_floor):
        surge = registration.surge
        return cls(
            baseline_days=surge.baseline_days,
            trailing_hours=surge.trailing_hours,
            end_quiet_hours=surge.end_quiet_hours,
            refractory_hours=surge.refractory_hours,
            max_duration_horizons=surge.max_duration_horizons,
            calendar_utc_offset_minutes=registration.calendar_utc_offset_minutes,
            c_min=c_min,
            k_floor=k_floor,
        )


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
        self._cursor = VisibilityCursor(observations, observed_at=lambda row: row.visible_at)
        self._offset = offset
        self.published = []
        self.daily = Counter()
        # Set when a newly visible row belongs to a day before the current tick's day.
        self.past_changed = False

    def local_date(self, moment) -> date:
        return (moment + self._offset).date()

    def advance(self, tick):
        today = self.local_date(tick)
        for row in self._cursor.advance(tick):
            insort(self.published, row.published_at)
            day = self.local_date(row.published_at)
            self.daily[day] += 1
            self.past_changed |= day < today

    def count_since(self, moment):
        # Every visible row was published at or before the current tick.
        return len(self.published) - bisect_left(self.published, moment)

    def trailing(self, tick, window):
        # Rows published in (tick - window, tick].
        return len(self.published) - bisect_right(self.published, tick - window)


class _CellTracker:
    """The per-cell episode state machine; it reads the shared as-of series."""

    def __init__(self, cell, rules, end):
        self.cell = cell
        self.rules = rules
        self.end = end
        # A daily baseline scaled to the trailing window it is compared with.
        self.scale = rules.trailing_hours / 24
        self.horizon = timedelta(hours=cell.horizon_hours)
        self.max_duration = self.horizon * rules.max_duration_horizons
        self.refractory = timedelta(hours=rules.refractory_hours)
        self.current = None
        self.last_end = None
        self.episodes = []

    def step(self, tick, series, count, baseline):
        expected = baseline * self.scale
        state = self.current
        if state is None:
            if self.last_end is not None and tick - self.last_end < self.refractory:
                return
            if count >= self.cell.onset_multiplier * expected and count >= self.rules.c_min:
                scaled = self.cell.size_multiplier * baseline
                k = max(scaled, self.rules.k_floor)
                self.current = _Open(tick, baseline, k, scaled < self.rules.k_floor)
            return
        size = series.count_since(state.onset_at) - state.baseline * ((tick - state.onset_at) / DAY)
        if state.tau_k is None:
            if size >= state.k:
                state.tau_k = tick
                state.overshoot = size / state.k
                if size >= 2 * state.k:
                    # First known at 2k: no forecast is possible and no later
                    # crossing is recorded.
                    state.detected_at_crossing = True
                    state.crossed_2k_at = tick
        elif (
            state.crossed_2k_at is None
            and tick <= state.tau_k + self.horizon
            and size >= 2 * state.k
        ):
            state.crossed_2k_at = tick
        # The end rule uses the current rolling baseline, not the frozen one. A zero
        # baseline is returned to only by a zero count (operator decision, 2026-10-02).
        quiet = count < expected or (expected == 0 and count == 0)
        state.quiet_hours = state.quiet_hours + 1 if quiet else 0
        if state.quiet_hours >= self.rules.end_quiet_hours:
            self._close(tick, "quiet")
        elif tick - state.onset_at >= self.max_duration:
            self._close(tick, "max_duration")

    def _close(self, ended_at, reason):
        self.episodes.append(self._episode(self.current, ended_at, reason))
        self.current, self.last_end = None, ended_at

    def finish(self):
        if self.current is not None:
            self.episodes.append(self._episode(self.current, None, "open"))
            self.current = None
        return tuple(self.episodes)

    def _episode(self, state, ended_at, reason):
        if state.detected_at_crossing:
            resolves_at, label = state.tau_k, "detected_at_crossing"
        elif state.tau_k is None:
            resolves_at, label = None, "open" if reason == "open" else "below_k"
        else:
            # Both classes resolve at tau_k + H; later than the data is censored.
            resolves_at = state.tau_k + self.horizon
            if resolves_at > self.end:
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


def detect_with_rules(observations, rules, cells, *, start, end):
    """Episodes per cell for one topic series under explicit detection rules."""
    if type(rules) is not Rules:
        raise ValueError("Validated detection rules are required")
    cells = tuple(dict.fromkeys(cells))
    if not cells or any(type(cell) is not Cell for cell in cells):
        raise ValueError("At least one registered cell is required")
    start, end = whole_hour(start), whole_hour(end)
    if end <= start:
        raise ValueError("The evaluation span must be positive")
    offset = timedelta(minutes=rules.calendar_utc_offset_minutes)
    series = _AsOfSeries(tuple(observations), offset)

    # Baselines use whole local days inside the data only (the burn-in).
    first_local = start + offset
    first_day = first_local.date()
    if first_local.time() != time(0):
        first_day += DAY
    trailing = timedelta(hours=rules.trailing_hours)
    cached = {}

    def baseline_at(tick):
        # Past daily counts change only with a new day or a late row for a past day.
        today = series.local_date(tick)
        if series.past_changed or cached.get("day") != today:
            days = [today - DAY * i for i in range(1, rules.baseline_days + 1)]
            value = None
            if days[-1] >= first_day:
                value = float(median(series.daily[day] for day in days))
            cached.update(day=today, value=value)
            series.past_changed = False
        return cached["value"]

    trackers = [_CellTracker(cell, rules, end) for cell in cells]
    tick = start
    while tick < end:
        tick += HOUR
        series.advance(tick)
        baseline = baseline_at(tick)
        if baseline is None:
            continue
        count = series.trailing(tick, trailing)
        for tracker in trackers:
            tracker.step(tick, series, count, baseline)
    return {tracker.cell: tracker.finish() for tracker in trackers}


def detect_grid(observations, locked, cells, *, start, end):
    """Episodes per registered grid cell for one topic series, in a single pass."""
    rules = Rules.from_locked(locked)
    grid = set(locked.grid)
    cells = tuple(cells)
    if any(type(cell) is not Cell or cell not in grid for cell in cells):
        raise ValueError("The cell is not in the registered grid")
    return detect_with_rules(observations, rules, cells, start=start, end=end)


def detect_episodes(observations, locked, cell, *, start, end):
    """Return the episodes of one topic series for one registered grid cell."""
    return detect_grid(observations, locked, (cell,), start=start, end=end)[cell]
