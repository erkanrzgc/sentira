"""Strict TOML input for the registered collection policy P (BACKTEST 0.3).

The policy fixes the discovery interval, the video ages at which threads are
polled and the paging limits. Live collection and replay read the same object.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from sentira.core.registration import digest, exact, slug

MAX_AGE_HOURS = 24 * 366
MAX_AGES = 32
# The provider returns at most 100 threads per page.
MAX_PAGE_SIZE = 100
MAX_PAGE_CAP = 1000


def bounded(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("A bounded integer is required")
    return value


@dataclass(frozen=True, slots=True)
class CollectionPolicy:
    mode: str
    version: str
    discovery_interval_hours: int
    poll_ages_hours: tuple[int, ...]
    page_size: int
    page_cap: int

    @classmethod
    def from_mapping(cls, raw):
        keys = "mode version discovery_interval_hours poll_ages_hours page_size page_cap"
        exact(raw, keys.split())
        if raw["mode"] != "synthetic":
            raise ValueError("Only synthetic collection policies are supported")
        interval = bounded(raw["discovery_interval_hours"], 1, 24)
        if 24 % interval:
            raise ValueError("The discovery interval must divide a day")
        ages = raw["poll_ages_hours"]
        if not isinstance(ages, list) or not 0 < len(ages) <= MAX_AGES:
            raise ValueError("A bounded, non-empty list of poll ages is required")
        ages = tuple(bounded(age, 1, MAX_AGE_HOURS) for age in ages)
        if any(later <= earlier for earlier, later in zip(ages, ages[1:], strict=False)):
            raise ValueError("Poll ages must be strictly increasing")
        return cls(
            mode=raw["mode"],
            version=slug(raw["version"]),
            discovery_interval_hours=interval,
            poll_ages_hours=ages,
            page_size=bounded(raw["page_size"], 1, MAX_PAGE_SIZE),
            page_cap=bounded(raw["page_cap"], 1, MAX_PAGE_CAP),
        )

    @property
    def sha256(self):
        return digest(self)

    @property
    def per_poll_limit(self):
        """Threads one poll can return: the page cap times the page size."""
        return self.page_size * self.page_cap


def load_collection_policy(path):
    with Path(path).open("rb") as stream:
        return CollectionPolicy.from_mapping(tomllib.load(stream))
