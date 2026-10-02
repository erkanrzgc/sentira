"""Strict TOML input for the quota policy of the metered client (BACKTEST B).

The policy fixes the daily allocation, its reservations, the purposes that may
overflow into the buffer, the quota-day boundary and the registered endpoints
with their unit costs. Only read-only list methods can be registered, and search
is excluded by design.
"""

import re
import tomllib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import digest, exact, sequence, slug

PURPOSES = ("live", "retrieval", "survival")
POOLS = (*PURPOSES, "buffer")
# Search draws on a separate provider bucket and is never part of the registered set.
EXCLUDED_ENDPOINTS = frozenset({"search.list"})
ENDPOINT = re.compile(r"[a-z][A-Za-z]{0,63}\.list")
MAX_DAILY_UNITS = 10**9


def units(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("A bounded integer number of units is required")
    return value


def endpoint_name(value):
    if not isinstance(value, str) or ENDPOINT.fullmatch(value) is None:
        raise ValueError("Only read-only list methods can be registered")
    if value in EXCLUDED_ENDPOINTS:
        raise ValueError("The endpoint is excluded from the registered set")
    return value


@dataclass(frozen=True, slots=True)
class QuotaPolicy:
    mode: str
    version: str
    daily_units: int
    quota_day_utc_offset_minutes: int
    reservations: tuple[tuple[str, int], ...]
    buffer_purposes: tuple[str, ...]
    endpoints: tuple[tuple[str, int], ...]

    @classmethod
    def from_mapping(cls, raw):
        keys = "mode version daily_units quota_day_utc_offset_minutes reservations buffer endpoints"
        exact(raw, keys.split())
        if raw["mode"] != "synthetic":
            raise ValueError("Only synthetic quota policies are supported")
        daily = units(raw["daily_units"], 1, MAX_DAILY_UNITS)
        offset = raw["quota_day_utc_offset_minutes"]
        if type(offset) is not int or not -840 <= offset <= 840 or offset % 15:
            raise ValueError("The quota-day offset must be a multiple of 15 minutes within a day")

        reserved = exact(raw["reservations"], POOLS)
        reservations = tuple((pool, units(reserved[pool], 0, daily)) for pool in POOLS)
        if sum(value for _, value in reservations) != daily:
            raise ValueError("The reservations must sum to the daily units")

        purposes = sequence(exact(raw["buffer"], ("purposes",))["purposes"], slug)
        if any(purpose not in PURPOSES for purpose in purposes):
            raise ValueError("Only collection purposes may draw on the buffer")

        registered = raw["endpoints"]
        if not isinstance(registered, dict) or not registered:
            raise ValueError("At least one endpoint must be registered")
        endpoints = tuple(
            (endpoint_name(name), units(cost, 1, daily))
            for name, cost in sorted(registered.items())
        )
        return cls(
            mode=raw["mode"],
            version=slug(raw["version"]),
            daily_units=daily,
            quota_day_utc_offset_minutes=offset,
            reservations=reservations,
            buffer_purposes=tuple(sorted(purposes)),
            endpoints=endpoints,
        )

    @property
    def sha256(self):
        return digest(self)

    def reservation(self, pool):
        return dict(self.reservations)[pool]

    def cost(self, endpoint):
        """Units for one call; an unregistered endpoint is refused."""
        cost = dict(self.endpoints).get(endpoint) if isinstance(endpoint, str) else None
        if cost is None:
            raise ValueError("The endpoint is not in the registered set")
        return cost

    def quota_day(self, moment):
        """The quota day containing a moment, at the registered offset from UTC."""
        try:
            local = utc(moment) + timedelta(minutes=self.quota_day_utc_offset_minutes)
        except OverflowError:
            raise ValueError("The quota day cannot be represented") from None
        return local.date().isoformat()


def load_quota_policy(path):
    with Path(path).open("rb") as stream:
        return QuotaPolicy.from_mapping(tomllib.load(stream))
