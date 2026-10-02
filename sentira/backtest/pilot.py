"""Pilot registration, locked before any pilot collection (BACKTEST A.9).

The registration fixes the stratified sample and its seeded selection, the
history and live spans, a hard quota ceiling and the adaptations the pilot may
make. Strata name channel types only, so the schema has nowhere to put a counter.
The lock binds the pilot to the collection policy, the quota policy and the
volume assumptions it was sized with, and is refused once collection has started
or when the projected cost exceeds the ceiling.
"""

import json
import tomllib
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from sentira.collectors.cost import DAYS_PER_YEAR, ceil_divide, project
from sentira.config.collection import CollectionPolicy, load_collection_policy
from sentira.config.quota import QuotaPolicy, load_quota_policy
from sentira.config.volume import VolumeAssumptions, load_volume
from sentira.core.document import utc
from sentira.core.registration import digest, exact, integer, sequence, slug

# Every permitted adaptation is named here; anything else is a silent relaxation.
ADAPTATIONS = frozenset(
    {"replace_unreachable_channel_within_stratum", "shorten_history_to_ceiling"}
)
SELECTION_METHODS = frozenset({"seeded_random"})
MAX_PILOT_CHANNELS = 60
MAX_HISTORY_DAYS = 90
# The job latency needs at least seven days of live running (BACKTEST B).
MIN_LIVE_DAYS = 7
MAX_LIVE_DAYS = 60


@dataclass(frozen=True, slots=True)
class Stratum:
    name: str
    channel_type: str
    channels: int

    def __post_init__(self):
        slug(self.name)
        slug(self.channel_type)
        integer(self.channels, 1, MAX_PILOT_CHANNELS)


@dataclass(frozen=True, slots=True)
class PilotRegistration:
    mode: str
    version: str
    registered_at: datetime
    collection_start: datetime
    history_days: int
    live_days: int
    quota_ceiling_units: int
    adaptations: tuple[str, ...]
    selection_method: str
    selection_seed: int
    strata: tuple[Stratum, ...]

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic pilot registrations are supported")
        slug(self.version)
        if utc(self.registered_at) > utc(self.collection_start):
            raise ValueError("A pilot is registered before its collection starts")
        integer(self.history_days, 1, MAX_HISTORY_DAYS)
        integer(self.live_days, MIN_LIVE_DAYS, MAX_LIVE_DAYS)
        integer(self.quota_ceiling_units, 1, 10**9)
        if type(self.adaptations) is not tuple or any(
            item not in ADAPTATIONS for item in self.adaptations
        ):
            raise ValueError("Only registered adaptations are permitted")
        if self.selection_method not in SELECTION_METHODS:
            raise ValueError("Unsupported selection method")
        integer(self.selection_seed, 0, 2**63 - 1)
        strata = self.strata
        if type(strata) is not tuple or not strata:
            raise ValueError("At least one stratum is required")
        if any(type(stratum) is not Stratum for stratum in strata):
            raise ValueError("Validated strata are required")
        if len({stratum.name for stratum in strata}) != len(strata):
            raise ValueError("Stratum names must be unique")
        if self.total_channels > MAX_PILOT_CHANNELS:
            raise ValueError("The pilot sample is limited to a small number of channels")

    @property
    def total_channels(self):
        return sum(stratum.channels for stratum in self.strata)

    @classmethod
    def from_mapping(cls, raw):
        keys = (
            "mode version registered_at collection_start history_days live_days "
            "quota_ceiling_units adaptations selection strata"
        )
        exact(raw, keys.split())
        selection = exact(raw["selection"], ("method", "seed"))
        strata = raw["strata"]
        if not isinstance(strata, list):
            raise ValueError("Strata must be a list")
        return cls(
            mode=raw["mode"],
            version=raw["version"],
            registered_at=raw["registered_at"],
            collection_start=raw["collection_start"],
            history_days=raw["history_days"],
            live_days=raw["live_days"],
            quota_ceiling_units=raw["quota_ceiling_units"],
            adaptations=tuple(sorted(sequence(raw["adaptations"], slug))),
            selection_method=selection["method"],
            selection_seed=selection["seed"],
            strata=tuple(
                Stratum(**exact(stratum, ("name", "channel_type", "channels")))
                for stratum in strata
            ),
        )


def load_pilot(path):
    with Path(path).open("rb") as stream:
        return PilotRegistration.from_mapping(tomllib.load(stream))


def projected_units(pilot, policy, quota, volume):
    """Calculated units of the whole pilot: live days plus the history span."""
    result = project(policy, quota, replace(volume, channels=pilot.total_channels))
    history = ceil_divide(
        result.retrieval_units_per_history_year * pilot.history_days, DAYS_PER_YEAR
    )
    return result.live_units * pilot.live_days + history


@dataclass(frozen=True, slots=True)
class LockedPilot:
    pilot: PilotRegistration
    policy: CollectionPolicy
    quota: QuotaPolicy
    volume: VolumeAssumptions
    pilot_sha256: str
    policy_sha256: str
    quota_sha256: str
    volume_sha256: str
    locked_at: datetime
    projected_units: int

    def __post_init__(self):
        if (
            type(self.pilot) is not PilotRegistration
            or type(self.policy) is not CollectionPolicy
            or type(self.quota) is not QuotaPolicy
            or type(self.volume) is not VolumeAssumptions
        ):
            raise ValueError("Validated pilot, policy, quota and volume inputs are required")
        for name in ("pilot", "policy", "quota", "volume"):
            if getattr(self, f"{name}_sha256") != digest(getattr(self, name)):
                raise ValueError(f"The {name} file does not match the pilot lock")
        if utc(self.locked_at) > utc(self.pilot.collection_start):
            raise ValueError("A pilot is locked before any pilot collection")
        expected = projected_units(self.pilot, self.policy, self.quota, self.volume)
        if self.projected_units != expected:
            raise ValueError("The projected pilot cost does not reproduce")
        if expected > self.pilot.quota_ceiling_units:
            raise ValueError("The projected pilot cost exceeds its quota ceiling")


def pilot_lock_text(pilot, policy, quota, volume, *, locked_at):
    locked_at = utc(locked_at)
    units = projected_units(pilot, policy, quota, volume)
    locked = LockedPilot(
        pilot,
        policy,
        quota,
        volume,
        digest(pilot),
        digest(policy),
        digest(quota),
        digest(volume),
        locked_at,
        units,
    )
    record = {
        "locked_at": locked.locked_at.isoformat(),
        "pilot_sha256": locked.pilot_sha256,
        "policy_sha256": locked.policy_sha256,
        "projected_units": locked.projected_units,
        "quota_sha256": locked.quota_sha256,
        "schema": 1,
        "volume_sha256": locked.volume_sha256,
    }
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def _inputs(pilot_path, policy_path, quota_path, volume_path):
    return (
        load_pilot(pilot_path),
        load_collection_policy(policy_path),
        load_quota_policy(quota_path),
        load_volume(volume_path),
    )


def write_pilot_lock(pilot_path, policy_path, quota_path, volume_path, lock_path, *, locked_at):
    inputs = _inputs(pilot_path, policy_path, quota_path, volume_path)
    content = pilot_lock_text(*inputs, locked_at=locked_at)
    # Exclusive creation: an existing pilot lock is never replaced.
    with Path(lock_path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def load_pilot_lock(pilot_path, policy_path, quota_path, volume_path, lock_path):
    inputs = _inputs(pilot_path, policy_path, quota_path, volume_path)
    keys = "locked_at pilot_sha256 policy_sha256 projected_units quota_sha256 schema volume_sha256"
    try:
        record = exact(json.loads(Path(lock_path).read_text(encoding="utf-8")), keys.split())
        locked_at = utc(datetime.fromisoformat(record["locked_at"]))
    except (json.JSONDecodeError, TypeError):
        raise ValueError("The pilot lock is not readable") from None
    if record["schema"] != 1:
        raise ValueError("Unsupported pilot lock schema")
    return LockedPilot(
        *inputs,
        record["pilot_sha256"],
        record["policy_sha256"],
        record["quota_sha256"],
        record["volume_sha256"],
        locked_at,
        record["projected_units"],
    )
