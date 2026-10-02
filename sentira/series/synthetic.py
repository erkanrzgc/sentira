"""Compact synthetic topic series: segments that expand into hourly rows.

Each segment adds `per_hour` rows at half past every hour for `hours` hours,
visible after `delay_hours`. The format describes fictional fixtures only.
"""

import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import digest, exact, slug
from sentira.series.episodes import Observation, whole_hour

MAX_ROWS = 2_000_000


def bounded(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("A bounded integer is required")
    return value


@dataclass(frozen=True, slots=True)
class SyntheticSeries:
    start: datetime
    end: datetime
    topics: dict
    sha256: str


def expand(segment):
    exact(segment, ("first", "hours", "per_hour"), ("delay_hours",))
    first = utc(segment["first"])
    hours = bounded(segment["hours"], 1, 24 * 400)
    per_hour = bounded(segment["per_hour"], 0, 1000)
    delay = timedelta(hours=bounded(segment.get("delay_hours", 0), 0, 24 * 30))
    rows = []
    for hour in range(hours):
        published = first + timedelta(hours=hour, minutes=30)
        rows.extend(Observation(published, published + delay) for _ in range(per_hour))
    return rows


def parse_series(raw):
    exact(raw, ("mode", "start", "end", "topics"))
    if raw["mode"] != "synthetic":
        raise ValueError("Only synthetic series are supported")
    start, end = whole_hour(raw["start"]), whole_hour(raw["end"])
    if end <= start or not isinstance(raw["topics"], list) or not raw["topics"]:
        raise ValueError("A positive span and at least one topic are required")
    topics, total = {}, 0
    for topic in raw["topics"]:
        exact(topic, ("id", "segments"))
        name = slug(topic["id"])
        if name in topics or not isinstance(topic["segments"], list):
            raise ValueError("Topics need unique identifiers and segment arrays")
        rows = [row for segment in topic["segments"] for row in expand(segment)]
        total += len(rows)
        if total > MAX_ROWS:
            raise ValueError("The synthetic series is too large")
        topics[name] = tuple(rows)
    return SyntheticSeries(start, end, topics, digest(raw))


def load_series(path):
    with Path(path).open("rb") as stream:
        return parse_series(tomllib.load(stream))
