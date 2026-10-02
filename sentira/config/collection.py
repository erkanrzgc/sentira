"""Strict TOML input for the registered collection policy P (BACKTEST 0.3).

The policy fixes the discovery interval, the video ages at which threads are
polled and the paging limits. Live collection and replay read the same object.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from sentira.core.registration import digest, exact, integer, slug

MAX_AGE_HOURS = 24 * 366
MAX_AGES = 32
# The provider returns at most 100 threads per page.
MAX_PAGE_SIZE = 100
MAX_PAGE_CAP = 1000


@dataclass(frozen=True, slots=True)
class CollectionPolicy:
    mode: str
    version: str
    discovery_interval_hours: int
    poll_ages_hours: tuple[int, ...]
    page_size: int
    page_cap: int

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic collection policies are supported")
        slug(self.version)
        if 24 % integer(self.discovery_interval_hours, 1, 24):
            raise ValueError("The discovery interval must divide a day")
        ages = self.poll_ages_hours
        if type(ages) is not tuple or not 0 < len(ages) <= MAX_AGES:
            raise ValueError("A bounded, non-empty tuple of poll ages is required")
        for age in ages:
            integer(age, 1, MAX_AGE_HOURS)
        if any(later <= earlier for earlier, later in zip(ages, ages[1:], strict=False)):
            raise ValueError("Poll ages must be strictly increasing")
        integer(self.page_size, 1, MAX_PAGE_SIZE)
        integer(self.page_cap, 1, MAX_PAGE_CAP)

    @classmethod
    def from_mapping(cls, raw):
        keys = "mode version discovery_interval_hours poll_ages_hours page_size page_cap"
        exact(raw, keys.split())
        if not isinstance(raw["poll_ages_hours"], list):
            raise ValueError("Poll ages must be a list")
        return cls(**{**raw, "poll_ages_hours": tuple(raw["poll_ages_hours"])})

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
