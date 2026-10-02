"""Strict TOML input for the volume assumptions of the quota cost projection.

Every value is an assumption until the first live run measures it. The cumulative
shares give the fraction of a video's threads published by each poll age of the
collection policy, in the same order.
"""

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sentira.core.registration import digest, exact, integer, slug

MAX_SHARES = 32
# The provider lists at most 50 playlist items per page.
MAX_PLAYLIST_PAGE_SIZE = 50


def share(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("A share between 0 and 1 is required")
    return value


@dataclass(frozen=True, slots=True)
class VolumeAssumptions:
    mode: str
    version: str
    channels: int
    videos_per_channel_day: int
    threads_per_video: int
    cumulative_share_by_age: tuple[float, ...]
    playlist_page_size: int

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic volume assumptions are supported")
        slug(self.version)
        integer(self.channels, 1, 100_000)
        integer(self.videos_per_channel_day, 0, 10_000)
        integer(self.threads_per_video, 0, 10**8)
        shares = self.cumulative_share_by_age
        if type(shares) is not tuple or not 0 < len(shares) <= MAX_SHARES:
            raise ValueError("A bounded, non-empty tuple of shares is required")
        for value in shares:
            share(value)
        if any(later < earlier for earlier, later in zip(shares, shares[1:], strict=False)):
            raise ValueError("Cumulative shares cannot decrease")
        integer(self.playlist_page_size, 1, MAX_PLAYLIST_PAGE_SIZE)

    @classmethod
    def from_mapping(cls, raw):
        keys = (
            "mode version channels videos_per_channel_day threads_per_video "
            "cumulative_share_by_age playlist_page_size"
        )
        exact(raw, keys.split())
        if not isinstance(raw["cumulative_share_by_age"], list):
            raise ValueError("Cumulative shares must be a list")
        return cls(**{**raw, "cumulative_share_by_age": tuple(raw["cumulative_share_by_age"])})

    @property
    def sha256(self):
        return digest(self)


def load_volume(path):
    with Path(path).open("rb") as stream:
        return VolumeAssumptions.from_mapping(tomllib.load(stream))
