"""Pilot registration, locked before any pilot collection (BACKTEST A.9).

The registration fixes the stratified sample, drawn by a registered seed from a
frozen channel frame, the history and live spans, a hard quota ceiling and the
adaptations the pilot may make. Strata name channel types only, so the schema has
nowhere to put a counter. The lock binds the pilot to the channel frame, the
collection policy, the quota policy, the volume assumptions and the topic
taxonomy, records the drawn sample and the projected cost, and is refused outside
the registration-to-start window, above the ceiling, or before the taxonomy was
frozen.
"""

import json
import random
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from sentira.backtest.registration import read_toml
from sentira.collectors.cost import project, retrieval_units
from sentira.config.channels import ChannelFrame, load_channel_frame
from sentira.config.collection import CollectionPolicy, load_collection_policy
from sentira.config.quota import QuotaPolicy, load_quota_policy
from sentira.config.taxonomy import Taxonomy, load_taxonomy
from sentira.config.volume import VolumeAssumptions, load_volume
from sentira.core.document import utc
from sentira.core.registration import digest, exact, integer, sequence, slug

# Every permitted adaptation is named here; anything else is a silent relaxation.
ADAPTATIONS = frozenset(
    {"replace_unreachable_channel_within_stratum", "shorten_history_to_ceiling"}
)
SELECTION_METHODS = frozenset({"seeded_random"})
# A declared lock time is the operator's statement; a system time is the clock's.
LOCK_TIME_SOURCES = frozenset({"declared", "system"})
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
    selection_frame_version: str
    strata: tuple[Stratum, ...]

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic pilot registrations are supported")
        slug(self.version)
        object.__setattr__(self, "registered_at", utc(self.registered_at))
        object.__setattr__(self, "collection_start", utc(self.collection_start))
        if self.registered_at > self.collection_start:
            raise ValueError("A pilot is registered before its collection starts")
        integer(self.history_days, 1, MAX_HISTORY_DAYS)
        integer(self.live_days, MIN_LIVE_DAYS, MAX_LIVE_DAYS)
        integer(self.quota_ceiling_units, 1, 10**9)
        adaptations = self.adaptations
        if type(adaptations) is not tuple or list(adaptations) != sorted(set(adaptations)):
            raise ValueError("Adaptations must be a sorted tuple without duplicates")
        if any(item not in ADAPTATIONS for item in adaptations):
            raise ValueError("Only registered adaptations are permitted")
        if self.selection_method not in SELECTION_METHODS:
            raise ValueError("Unsupported selection method")
        integer(self.selection_seed, 0, 2**63 - 1)
        slug(self.selection_frame_version)
        strata = self.strata
        if type(strata) is not tuple or not strata:
            raise ValueError("At least one stratum is required")
        if any(type(stratum) is not Stratum for stratum in strata):
            raise ValueError("Validated strata are required")
        if len({stratum.name for stratum in strata}) != len(strata):
            raise ValueError("Stratum names must be unique")
        # Strata of one type would compete for the same candidates.
        if len({stratum.channel_type for stratum in strata}) != len(strata):
            raise ValueError("Each stratum must have its own channel type")
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
        selection = exact(raw["selection"], ("method", "seed", "frame_version"))
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
            selection_frame_version=selection["frame_version"],
            strata=tuple(
                Stratum(**exact(stratum, ("name", "channel_type", "channels")))
                for stratum in strata
            ),
        )


def load_pilot(path):
    return PilotRegistration.from_mapping(read_toml(path))


def select_sample(pilot, frame):
    """The channels drawn for each stratum from the frame as it stood at registration."""
    if type(pilot) is not PilotRegistration or type(frame) is not ChannelFrame:
        raise ValueError("A validated pilot and channel frame are required")
    if frame.version != pilot.selection_frame_version:
        raise ValueError("The channel frame is not the registered one")
    sample = []
    for stratum in pilot.strata:
        candidates = frame.candidates(stratum.channel_type, as_of=pilot.registered_at)
        if len(candidates) < stratum.channels:
            raise ValueError("A stratum has fewer candidate channels than it registers")
        generator = random.Random(f"{pilot.selection_seed}:{stratum.name}")
        sample.append((stratum.name, tuple(sorted(generator.sample(candidates, stratum.channels)))))
    # Ordered by stratum name, as the lock records it.
    return tuple(sorted(sample))


def projected_units(pilot, policy, quota, volume):
    """Calculated units of the whole pilot: the live days plus the history span."""
    sampled = replace(volume, channels=pilot.total_channels)
    live = project(policy, quota, sampled).live_units * pilot.live_days
    return live + retrieval_units(policy, quota, sampled, pilot.history_days)


INPUTS = ("pilot", "frame", "policy", "quota", "volume", "taxonomy")
SCHEMA = 2


@dataclass(frozen=True, slots=True)
class LockedPilot:
    pilot: PilotRegistration
    frame: ChannelFrame
    policy: CollectionPolicy
    quota: QuotaPolicy
    volume: VolumeAssumptions
    taxonomy: Taxonomy
    digests: tuple[str, ...]
    sample: tuple[tuple[str, tuple[str, ...]], ...]
    locked_at: datetime
    locked_at_source: str
    projected_units: int

    def __post_init__(self):
        kinds = (
            PilotRegistration,
            ChannelFrame,
            CollectionPolicy,
            QuotaPolicy,
            VolumeAssumptions,
            Taxonomy,
        )
        values = tuple(getattr(self, name) for name in INPUTS)
        if any(type(value) is not kind for value, kind in zip(values, kinds, strict=True)):
            raise ValueError(
                "Validated pilot, frame, policy, quota, volume and taxonomy inputs are required"
            )
        if self.digests != tuple(digest(value) for value in values):
            raise ValueError("An input file does not match the pilot lock")
        if self.sample != select_sample(self.pilot, self.frame):
            raise ValueError("The recorded sample does not reproduce")
        if self.locked_at_source not in LOCK_TIME_SOURCES:
            raise ValueError("Unknown lock time source")
        locked_at = utc(self.locked_at)
        if not self.pilot.registered_at <= locked_at <= self.pilot.collection_start:
            raise ValueError("A pilot is locked after registration and before any collection")
        # Topics are fixed before the pilot sees data, so none is written with hindsight.
        if self.taxonomy.frozen_at > locked_at:
            raise ValueError("The taxonomy must be frozen before the pilot is locked")
        if type(self.projected_units) is not int:
            raise ValueError("The projected pilot cost must be a whole number of units")
        expected = projected_units(self.pilot, self.policy, self.quota, self.volume)
        if self.projected_units != expected:
            raise ValueError("The projected pilot cost does not reproduce")
        if expected > self.pilot.quota_ceiling_units:
            raise ValueError("The projected pilot cost exceeds its quota ceiling")


def lock_pilot(pilot, frame, policy, quota, volume, taxonomy, *, locked_at, source):
    """Validate and return the locked view; every check runs once, at construction."""
    values = (pilot, frame, policy, quota, volume, taxonomy)
    return LockedPilot(
        *values,
        digests=tuple(digest(value) for value in values),
        sample=select_sample(pilot, frame),
        locked_at=utc(locked_at),
        locked_at_source=source,
        projected_units=projected_units(pilot, policy, quota, volume),
    )


def pilot_lock_text(*values, locked_at, source):
    locked = lock_pilot(*values, locked_at=locked_at, source=source)
    record = {
        **{f"{name}_sha256": value for name, value in zip(INPUTS, locked.digests, strict=True)},
        "locked_at": locked.locked_at.isoformat(),
        "locked_at_source": locked.locked_at_source,
        "projected_units": locked.projected_units,
        "sample": {name: list(ids) for name, ids in locked.sample},
        "schema": SCHEMA,
    }
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def _inputs(pilot_path, frame_path, policy_path, quota_path, volume_path, taxonomy_path):
    return (
        load_pilot(pilot_path),
        load_channel_frame(frame_path),
        load_collection_policy(policy_path),
        load_quota_policy(quota_path),
        load_volume(volume_path),
        load_taxonomy(taxonomy_path),
    )


def write_pilot_lock(*paths, lock_path, locked_at, source):
    content = pilot_lock_text(*_inputs(*paths), locked_at=locked_at, source=source)
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: an existing pilot lock is never replaced.
    with Path(lock_path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def load_pilot_lock(*paths, lock_path):
    inputs = _inputs(*paths)
    keys = [f"{name}_sha256" for name in INPUTS]
    keys += ["locked_at", "locked_at_source", "projected_units", "sample", "schema"]
    try:
        record = exact(json.loads(Path(lock_path).read_text(encoding="utf-8")), keys)
        locked_at = utc(datetime.fromisoformat(record["locked_at"]))
        sample = tuple((name, tuple(ids)) for name, ids in record["sample"].items())
    except (json.JSONDecodeError, TypeError, AttributeError):
        raise ValueError("The pilot lock is not readable") from None
    if type(record["schema"]) is not int or record["schema"] != SCHEMA:
        raise ValueError("Unsupported pilot lock schema")
    return LockedPilot(
        *inputs,
        digests=tuple(record[key] for key in keys[: len(INPUTS)]),
        sample=sample,
        locked_at=locked_at,
        locked_at_source=record["locked_at_source"],
        projected_units=record["projected_units"],
    )
