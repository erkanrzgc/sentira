"""Strict TOML input for the volume assumptions of the quota cost projection.

Every value is an assumption until the first live run measures it. Threads per
video are given as strata, so that a heavy tail is costed as such rather than
through its mean. The cumulative shares give the fraction of a video's threads
published by each poll age of the collection policy, in the same order.
"""

import math
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from sentira.core.registration import digest, exact, integer, slug

MAX_SHARES = 32
MAX_STRATA = 16
# The provider lists at most 50 playlist items per page.
MAX_PLAYLIST_PAGE_SIZE = 50


def share(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("A share between 0 and 1 is required")
    return value


def exact_share(value):
    """The decimal value as written, so that shares sum exactly."""
    return Fraction(str(share(value)))


@dataclass(frozen=True, slots=True)
class VolumeAssumptions:
    mode: str
    version: str
    channels: int
    videos_per_channel_day: int
    # (share of videos, threads per video) pairs whose shares sum to one.
    thread_strata: tuple[tuple[float, int], ...]
    cumulative_share_by_age: tuple[float, ...]
    playlist_page_size: int
    # Reported by the provider's users, not verified (BACKTEST D.6).
    playlist_item_ceiling: int

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic volume assumptions are supported")
        slug(self.version)
        integer(self.channels, 1, 100_000)
        integer(self.videos_per_channel_day, 0, 10_000)
        strata = self.thread_strata
        if type(strata) is not tuple or not 0 < len(strata) <= MAX_STRATA:
            raise ValueError("A bounded, non-empty tuple of thread strata is required")
        if any(type(item) is not tuple or len(item) != 2 for item in strata):
            raise ValueError("Each stratum is a share of videos and a thread count")
        for weight, threads in strata:
            if exact_share(weight) == 0:
                raise ValueError("A stratum must hold some videos")
            integer(threads, 0, 10**8)
        if sum(exact_share(weight) for weight, _ in strata) != 1:
            raise ValueError("Stratum shares must sum to one")
        shares = self.cumulative_share_by_age
        if type(shares) is not tuple or not 0 < len(shares) <= MAX_SHARES:
            raise ValueError("A bounded, non-empty tuple of shares is required")
        for value in shares:
            share(value)
        if any(later < earlier for earlier, later in zip(shares, shares[1:], strict=False)):
            raise ValueError("Cumulative shares cannot decrease")
        integer(self.playlist_page_size, 1, MAX_PLAYLIST_PAGE_SIZE)
        integer(self.playlist_item_ceiling, 1, 10**9)

    @classmethod
    def from_mapping(cls, raw):
        keys = (
            "mode version channels videos_per_channel_day thread_strata "
            "cumulative_share_by_age playlist_page_size playlist_item_ceiling"
        )
        exact(raw, keys.split())
        strata, shares = raw["thread_strata"], raw["cumulative_share_by_age"]
        if not isinstance(strata, list) or not isinstance(shares, list):
            raise ValueError("Thread strata and cumulative shares must be lists")
        pairs = []
        for stratum in strata:
            exact(stratum, ("share_of_videos", "threads_per_video"))
            pairs.append((stratum["share_of_videos"], stratum["threads_per_video"]))
        return cls(
            **{**raw, "thread_strata": tuple(pairs), "cumulative_share_by_age": tuple(shares)}
        )

    @property
    def sha256(self):
        return digest(self)


def load_volume(path):
    with Path(path).open("rb") as stream:
        return VolumeAssumptions.from_mapping(tomllib.load(stream))
