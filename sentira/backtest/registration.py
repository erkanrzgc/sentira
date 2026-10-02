"""Locked surge definitions; counting refuses any registration that has changed.

Digests cover the canonical validated content, so comments and line endings do
not affect a lock while every definitional change does.
"""

import json
import math
import tomllib
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from itertools import product
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import digest, exact, sequence, slug


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("A bounded integer is required")
    return value


def multiplier(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 100:
        raise ValueError("A positive finite multiplier is required")
    return float(value)


def grid(values, item):
    result = sequence(values, item)
    if not result:
        raise ValueError("A grid needs at least one value")
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True, order=True)
class Cell:
    onset_multiplier: float
    size_multiplier: float
    horizon_hours: int


@dataclass(frozen=True, slots=True)
class SurgeDefinition:
    baseline_days: int
    trailing_hours: int
    refractory_hours: int
    end_quiet_hours: int
    max_duration_horizons: int
    onset_multipliers: tuple[float, ...]
    size_multipliers: tuple[float, ...]
    horizons_hours: tuple[int, ...]
    primary_onset_multiplier: float
    primary_size_multiplier: float
    fallback_few_positives: float
    fallback_few_negatives: float
    k_min: int
    reporting_floor: int
    week_floor: int

    @classmethod
    def from_mapping(cls, raw):
        keys = (
            "baseline_days trailing_hours refractory_hours end_quiet_hours "
            "max_duration_horizons onset_multipliers size_multipliers horizons_hours "
            "primary fallback floors"
        ).split()
        exact(raw, keys)
        primary = exact(raw["primary"], ("onset_multiplier", "size_multiplier"))
        fallback = exact(
            raw["fallback"], ("few_positives_size_multiplier", "few_negatives_size_multiplier")
        )
        floors = exact(raw["floors"], ("k_min", "reporting_floor", "week_floor"))
        result = cls(
            baseline_days=integer(raw["baseline_days"], 1, 366),
            trailing_hours=integer(raw["trailing_hours"], 1, 24 * 7),
            refractory_hours=integer(raw["refractory_hours"], 0, 24 * 90),
            end_quiet_hours=integer(raw["end_quiet_hours"], 1, 24 * 7),
            max_duration_horizons=integer(raw["max_duration_horizons"], 1, 10),
            onset_multipliers=grid(raw["onset_multipliers"], multiplier),
            size_multipliers=grid(raw["size_multipliers"], multiplier),
            horizons_hours=grid(raw["horizons_hours"], lambda v: integer(v, 1, 24 * 90)),
            primary_onset_multiplier=multiplier(primary["onset_multiplier"]),
            primary_size_multiplier=multiplier(primary["size_multiplier"]),
            fallback_few_positives=multiplier(fallback["few_positives_size_multiplier"]),
            fallback_few_negatives=multiplier(fallback["few_negatives_size_multiplier"]),
            k_min=integer(floors["k_min"], 1, 10**6),
            reporting_floor=integer(floors["reporting_floor"], 1, 10**6),
            week_floor=integer(floors["week_floor"], 1, 10**4),
        )
        if result.reporting_floor > result.k_min:
            raise ValueError("The reporting floor cannot exceed K_min")
        if result.primary_onset_multiplier not in result.onset_multipliers or any(
            value not in result.size_multipliers
            for value in (
                result.primary_size_multiplier,
                result.fallback_few_positives,
                result.fallback_few_negatives,
            )
        ):
            raise ValueError("Primary and fallback cells must lie in the registered grid")
        return result


@dataclass(frozen=True, slots=True)
class WalkForward:
    """Registered constants of BACKTEST A.5: history start D0 and first origin O1."""

    history_start: datetime
    burn_in_days: int
    training_days: int
    fold_days: int

    @classmethod
    def from_mapping(cls, raw):
        exact(raw, ("history_start", "burn_in_days", "training_days", "fold_days"))
        return cls(
            history_start=utc(raw["history_start"]),
            burn_in_days=integer(raw["burn_in_days"], 1, 366),
            training_days=integer(raw["training_days"], 1, 3660),
            fold_days=integer(raw["fold_days"], 1, 366),
        )

    @property
    def first_origin(self):
        # The pre-origin span [D0, O1) is never a test fold.
        return self.history_start + timedelta(days=self.burn_in_days + self.training_days)


@dataclass(frozen=True, slots=True)
class Registration:
    mode: str
    version: str
    registered_at: datetime
    calendar_utc_offset_minutes: int
    surge: SurgeDefinition
    walk_forward: WalkForward

    @classmethod
    def from_mapping(cls, raw):
        keys = "mode version registered_at calendar_utc_offset_minutes surge walk_forward".split()
        exact(raw, keys)
        if raw["mode"] != "synthetic":
            raise ValueError("Only synthetic registrations are supported")
        offset = integer(raw["calendar_utc_offset_minutes"], -840, 840)
        if offset % 15:
            raise ValueError("The calendar offset must be a multiple of 15 minutes")
        result = cls(
            mode=raw["mode"],
            version=slug(raw["version"]),
            registered_at=utc(raw["registered_at"]),
            calendar_utc_offset_minutes=offset,
            surge=SurgeDefinition.from_mapping(raw["surge"]),
            walk_forward=WalkForward.from_mapping(raw["walk_forward"]),
        )
        local_start = result.walk_forward.history_start + timedelta(minutes=offset)
        if local_start.time() != time(0):
            raise ValueError("The history start must fall on a local midnight")
        if result.walk_forward.burn_in_days < result.surge.baseline_days:
            raise ValueError("The burn-in must cover the baseline window")
        return result


@dataclass(frozen=True, slots=True)
class Measured:
    mode: str
    version: str
    registration_version: str
    c_min: int
    k_floor: int
    horizon_hours: int

    @classmethod
    def from_mapping(cls, raw):
        exact(raw, ("mode", "version", "registration_version", "c_min", "k_floor", "horizon_hours"))
        if raw["mode"] != "synthetic":
            raise ValueError("Only synthetic measured addenda are supported")
        return cls(
            mode=raw["mode"],
            version=slug(raw["version"]),
            registration_version=slug(raw["registration_version"]),
            c_min=integer(raw["c_min"], 1, 10**6),
            k_floor=integer(raw["k_floor"], 1, 10**6),
            horizon_hours=integer(raw["horizon_hours"], 1, 24 * 90),
        )


def read_toml(path):
    with Path(path).open("rb") as stream:
        return tomllib.load(stream)


def load_registration(path):
    return Registration.from_mapping(read_toml(path))


def load_measured(path):
    return Measured.from_mapping(read_toml(path))


@dataclass(frozen=True, slots=True)
class LockedRegistration:
    registration: Registration
    measured: Measured
    registration_sha256: str
    measured_sha256: str

    def __post_init__(self):
        if type(self.registration) is not Registration or type(self.measured) is not Measured:
            raise ValueError("Validated registration files are required")
        if self.measured.registration_version != self.registration.version:
            raise ValueError("The measured addendum belongs to another registration")
        if self.measured.horizon_hours not in self.registration.surge.horizons_hours:
            raise ValueError("The measured horizon must lie in the registered grid")
        if self.registration_sha256 != digest(self.registration):
            raise ValueError("The registration does not match its lock")
        if self.measured_sha256 != digest(self.measured):
            raise ValueError("The measured addendum does not match its lock")

    @property
    def primary_cell(self):
        surge = self.registration.surge
        return Cell(
            surge.primary_onset_multiplier,
            surge.primary_size_multiplier,
            self.measured.horizon_hours,
        )

    @property
    def grid(self):
        surge = self.registration.surge
        return tuple(
            Cell(*values)
            for values in product(
                surge.onset_multipliers, surge.size_multipliers, surge.horizons_hours
            )
        )


def lock_text(registration, measured):
    # Constructing the locked view validates cross-file consistency first.
    locked = LockedRegistration(registration, measured, digest(registration), digest(measured))
    record = {
        "measured_sha256": locked.measured_sha256,
        "registration_sha256": locked.registration_sha256,
        "schema": 1,
    }
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def write_lock(registration_path, measured_path, lock_path):
    content = lock_text(load_registration(registration_path), load_measured(measured_path))
    # Exclusive creation: an existing lock is never replaced.
    with Path(lock_path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def load_locked(registration_path, measured_path, lock_path):
    registration = load_registration(registration_path)
    measured = load_measured(measured_path)
    try:
        record = json.loads(Path(lock_path).read_text(encoding="utf-8"))
        exact(record, ("measured_sha256", "registration_sha256", "schema"))
    except json.JSONDecodeError:
        raise ValueError("The registration lock is not readable") from None
    if record["schema"] != 1:
        raise ValueError("Unsupported registration lock schema")
    return LockedRegistration(
        registration, measured, record["registration_sha256"], record["measured_sha256"]
    )
