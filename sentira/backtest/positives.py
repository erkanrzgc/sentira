"""Per-cell surge counts and the registered selection rule (BACKTEST A.3, A.6, B).

Counts are calculated on synthetic series. They carry no accuracy figure and no
claim about real discourse.
"""

from dataclasses import dataclass

from sentira.backtest.registration import Cell, LockedRegistration
from sentira.series.episodes import detect_episodes


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
class Selection:
    outcome: str
    cell: Cell | None
    reason: str


def count_cell(series, locked, cell, *, start, end):
    """Count one cell over topic series; eligible = detected + T1 classes + censored."""
    found = [
        episode
        for rows in series.values()
        for episode in detect_episodes(rows, locked, cell, start=start, end=end)
    ]
    eligible = [episode for episode in found if episode.tau_k is not None]
    population = [episode for episode in eligible if not episode.detected_at_crossing]
    positives = [episode for episode in population if episode.label == "positive"]
    weeks = {episode.tau_k.isocalendar()[:2] for episode in positives}
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


def count_grid(series, locked, *, start, end):
    return tuple(
        count_cell(series, locked, cell, start=start, end=end) for cell in sorted(locked.grid)
    )


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


def describe(cell):
    return (
        f"m = {cell.onset_multiplier:g}, κ = {cell.size_multiplier:g}, H = {cell.horizon_hours} h"
    )


def render_count(locked, series, counts, selection):
    registration, measured, surge = locked.registration, locked.measured, locked.registration.surge
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
        "Visibility: strict observation time; no replay reconstruction.",
        "",
        "## Registered selection",
        "",
        f"Outcome: {outcome}.",
        f"Reason: {selection.reason}.",
        f"Selected cell: {describe(selection.cell) if selection.cell else 'none'}.",
        f"Primary cell: {describe(locked.primary_cell)}.",
        f"K_min: {surge.k_min} per class; week floor: {surge.week_floor} weeks with a positive.",
        f"Below {surge.reporting_floor} per class, counts only are reported.",
        "",
        "## Counts per cell (calculated)",
        "",
        "Positive and negative exclude episodes detected at crossing. Eligible episodes",
        "reached k; censored episodes resolve after the end of the series.",
        "",
        "| m | κ | H (h) | Episodes | Eligible | Positive | Negative | Censored "
        "| Detected at crossing | k_floor binds | Weeks with a positive |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for count in counts:
        cell = count.cell
        lines.append(
            f"| {cell.onset_multiplier:g} | {cell.size_multiplier:g} | {cell.horizon_hours} "
            f"| {count.episodes} | {count.eligible} | {count.positive} | {count.negative} "
            f"| {count.censored} | {count.detected_at_crossing} | {count.k_floor_binds} "
            f"| {count.positive_weeks} |"
        )
    return "\n".join(lines) + "\n"
