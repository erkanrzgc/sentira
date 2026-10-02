"""Per-cell surge counts and the registered selection rule (BACKTEST A.3, A.6, B).

Counts are calculated on synthetic series. They carry no accuracy figure and no
claim about real discourse.
"""

from dataclasses import dataclass
from datetime import timedelta

from sentira.backtest.measurement import measure
from sentira.backtest.registration import Cell, LockedRegistration
from sentira.series.episodes import detect_grid


@dataclass(frozen=True, slots=True)
class CellCount:
    cell: Cell
    episodes: int
    eligible: int
    positive: int
    negative: int
    censored: int
    detected_at_crossing: int
    k_floor_binds: int
    positive_weeks: int


@dataclass(frozen=True, slots=True)
class SpanCounts:
    """Counts for the test span (from O1) and the pre-origin span [D0, O1)."""

    test: tuple[CellCount, ...]
    pre_origin: tuple[CellCount, ...]


@dataclass(frozen=True, slots=True)
class Selection:
    outcome: str
    cell: Cell | None
    reason: str


def span_time(episode):
    # An eligible episode belongs to the fold containing its tau_k (A.5).
    return episode.tau_k if episode.tau_k is not None else episode.onset_at


def summarise(cell, found, *, origin=None, fold_days=None):
    """Count one cell's episodes; eligible = detected + T1 classes + censored.

    With an origin, every episode must lie in the test span, and positive weeks
    count the distinct registered folds that contain a positive tau_k.
    """
    eligible = [episode for episode in found if episode.tau_k is not None]
    population = [episode for episode in eligible if not episode.detected_at_crossing]
    positives = [episode for episode in population if episode.label == "positive"]
    weeks = set()
    if origin is not None:
        if any(span_time(episode) < origin for episode in found):
            raise ValueError("Pre-origin episodes are never in a test fold")
        fold = timedelta(days=fold_days)
        weeks = {(episode.tau_k - origin) // fold for episode in positives}
    return CellCount(
        cell=cell,
        episodes=len(found),
        eligible=len(eligible),
        positive=len(positives),
        negative=sum(episode.label == "negative" for episode in population),
        censored=sum(episode.label == "censored" for episode in population),
        detected_at_crossing=len(eligible) - len(population),
        k_floor_binds=sum(episode.k_floor_binds for episode in eligible),
        positive_weeks=len(weeks),
    )


def count_grid(series, locked, *, start, end, cells=None):
    """Count cells over topic series by span; each topic is replayed once for all cells."""
    walk = locked.registration.walk_forward
    origin = walk.first_origin
    cells = tuple(sorted(locked.grid if cells is None else cells))
    found = {cell: [] for cell in cells}
    for rows in series.values():
        for cell, episodes in detect_grid(rows, locked, cells, start=start, end=end).items():
            found[cell].extend(episodes)
    test, pre_origin = [], []
    for cell in cells:
        later = [episode for episode in found[cell] if span_time(episode) >= origin]
        earlier = [episode for episode in found[cell] if span_time(episode) < origin]
        test.append(summarise(cell, later, origin=origin, fold_days=walk.fold_days))
        pre_origin.append(summarise(cell, earlier))
    return SpanCounts(tuple(test), tuple(pre_origin))


def count_series(series, locked):
    """Count a synthetic series whose pre-origin span reproduces the locked addendum."""
    # The addendum must be exactly what the registered rules give for this data;
    # measure() also refuses a series that does not start at D0 or reach O1.
    if measure(series, locked.registration) != locked.measured:
        raise ValueError("The measured addendum does not reproduce from the pre-origin span")
    return count_grid(series.topics, locked, start=series.start, end=series.end)


def select_cell(counts, locked):
    """Apply the registered primary-and-fallback rule; never promote another cell."""
    if type(locked) is not LockedRegistration:
        raise ValueError("A locked registration is required")
    surge = locked.registration.surge
    by_cell = {count.cell: count for count in counts}
    primary = locked.primary_cell
    if primary not in by_cell:
        raise ValueError("The primary cell has not been counted")
    first = by_cell[primary]
    k_min = surge.k_min
    short_positive, short_negative = first.positive < k_min, first.negative < k_min
    if short_positive and short_negative:
        return Selection("not_backtestable", None, "both classes below K_min in the primary cell")
    if not short_positive and not short_negative:
        outcome, chosen = "primary", first
    else:
        outcome = "fallback_few_positives" if short_positive else "fallback_few_negatives"
        size = surge.fallback_few_positives if short_positive else surge.fallback_few_negatives
        cell = Cell(primary.onset_multiplier, size, primary.horizon_hours)
        if cell not in by_cell:
            raise ValueError("The registered fallback cell has not been counted")
        chosen = by_cell[cell]
        if chosen.positive < k_min or chosen.negative < k_min:
            return Selection(
                "not_backtestable", None, "a class remains below K_min in the fallback cell"
            )
    if chosen.positive_weeks < surge.week_floor:
        return Selection("not_backtestable", None, "the week floor of positive weeks is not met")
    return Selection(outcome, chosen.cell, "both classes reach K_min and the week floor is met")


def share(count):
    if not count.eligible:
        return "0/0"
    percent = 100 * count.k_floor_binds / count.eligible
    return f"{count.k_floor_binds}/{count.eligible} ({percent:.1f}%)"


def describe(cell):
    return (
        f"m = {cell.onset_multiplier:g}, κ = {cell.size_multiplier:g}, H = {cell.horizon_hours} h"
    )


def table(counts, *, weeks):
    lines = [
        "| m | κ | H (h) | Episodes | Eligible | Positive | Negative | Censored "
        "| Detected at crossing | k_floor binds (of eligible) | Weeks with a positive |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for count in counts:
        cell = count.cell
        lines.append(
            f"| {cell.onset_multiplier:g} | {cell.size_multiplier:g} | {cell.horizon_hours} "
            f"| {count.episodes} | {count.eligible} | {count.positive} | {count.negative} "
            f"| {count.censored} | {count.detected_at_crossing} | {share(count)} "
            f"| {count.positive_weeks if weeks else 'n/a'} |"
        )
    return lines


def render_count(locked, series, counts, selection):
    registration, measured, surge = locked.registration, locked.measured, locked.registration.surge
    walk = registration.walk_forward
    outcome = {
        "primary": "primary cell",
        "fallback_few_positives": "registered fallback for too few positives",
        "fallback_few_negatives": "registered fallback for too few negatives",
        "not_backtestable": "not backtestable on current history",
    }[selection.outcome]
    lines = [
        "# SYNTHETIC surge count report",
        "",
        "Fictional series only. Every figure is calculated from supplied rows.",
        "No accuracy, forecast or real-world claim is made.",
        "",
        f"Registration: {registration.version}; SHA-256 {locked.registration_sha256}",
        f"Measured addendum: {measured.version}; SHA-256 {locked.measured_sha256}",
        f"Series SHA-256: {series.sha256}",
        f"Span: {series.start.isoformat()} to {series.end.isoformat()}",
        f"Topics: {len(series.topics)}",
        f"Calendar offset: {registration.calendar_utc_offset_minutes} minutes from UTC",
        f"History start D0: {walk.history_start.isoformat()}",
        f"First origin O1: {walk.first_origin.isoformat()}; test folds of {walk.fold_days} days",
        "Visibility: strict observation time; no replay reconstruction.",
        "",
        "## Registered selection",
        "",
        f"Outcome: {outcome}.",
        f"Reason: {selection.reason}.",
        f"Selected cell: {describe(selection.cell) if selection.cell else 'none'}.",
        f"Primary cell: {describe(locked.primary_cell)}.",
        f"K_min: {surge.k_min} per class; "
        f"week floor: {surge.week_floor} test folds with a positive.",
        f"Below {surge.reporting_floor} per class, counts only are reported.",
        "",
        "Positive and negative exclude episodes detected at crossing. Eligible episodes",
        "reached k; censored episodes resolve after the end of the series. An eligible",
        "episode belongs to the span and fold containing its tau_k.",
        "",
        "## Test span from O1 (calculated)",
        "",
        *table(counts.test, weeks=True),
        "",
        "## Pre-origin span [D0, O1) (calculated; never a test fold)",
        "",
        *table(counts.pre_origin, weeks=False),
    ]
    return "\n".join(lines) + "\n"
