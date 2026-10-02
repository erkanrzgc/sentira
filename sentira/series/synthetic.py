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
MAX_SEGMENTS = 10_000


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


@dataclass(frozen=True, slots=True)
class Segment:
    first: datetime
    hours: int
    per_hour: int
    delay: timedelta

    @classmethod
    def from_mapping(cls, raw):
        exact(raw, ("first", "hours", "per_hour"), ("delay_hours",))
        return cls(
            first=utc(raw["first"]),
            hours=bounded(raw["hours"], 1, 24 * 400),
            per_hour=bounded(raw["per_hour"], 0, 1000),
            delay=timedelta(hours=bounded(raw.get("delay_hours", 0), 0, 24 * 30)),
        )

    @property
    def size(self):
        return self.hours * self.per_hour

    def expand(self):
        try:
            # The latest visibility time must be representable before any row is built.
            self.first + timedelta(hours=self.hours, minutes=30) + self.delay
            rows = []
            for hour in range(self.hours):
                published = self.first + timedelta(hours=hour, minutes=30)
                visible = published + self.delay
                rows.extend(Observation(published, visible) for _ in range(self.per_hour))
            return rows
        except OverflowError:
            raise ValueError("Segment times cannot be represented") from None


def parse_series(raw):
    exact(raw, ("mode", "start", "end", "topics"))
    if raw["mode"] != "synthetic":
        raise ValueError("Only synthetic series are supported")
    start, end = whole_hour(raw["start"]), whole_hour(raw["end"])
    if end <= start or not isinstance(raw["topics"], list) or not raw["topics"]:
        raise ValueError("A positive span and at least one topic are required")
    segments, total = {}, 0
    for topic in raw["topics"]:
        exact(topic, ("id", "segments"))
        name = slug(topic["id"])
        if name in segments or not isinstance(topic["segments"], list):
            raise ValueError("Topics need unique identifiers and segment arrays")
        if len(topic["segments"]) > MAX_SEGMENTS:
            raise ValueError("A topic has too many segments")
        segments[name] = [Segment.from_mapping(segment) for segment in topic["segments"]]
        # Sizes are bounded arithmetically before any row is expanded.
        total += sum(segment.size for segment in segments[name])
        if total > MAX_ROWS:
            raise ValueError("The synthetic series is too large")
    topics = {
        name: tuple(row for segment in parts for row in segment.expand())
        for name, parts in segments.items()
    }
    return SyntheticSeries(start, end, topics, digest(raw))


def load_series(path):
    with Path(path).open("rb") as stream:
        return parse_series(tomllib.load(stream))
