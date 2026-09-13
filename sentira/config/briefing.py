"""Non-executable, immutable and strictly validated briefing configuration."""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import DOMAIN_IDS, digest, exact, sequence, slug, synthetic_url, text


@dataclass(frozen=True, slots=True)
class Domain:
    id: str
    label: str

    def __post_init__(self):
        if self.id not in DOMAIN_IDS:
            raise ValueError("Unsupported domain")
        text(self.label)


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    label: str
    url: str
    origin_group: str
    rights_record_id: str

    def __post_init__(self):
        for value in (self.id, self.origin_group, self.rights_record_id):
            slug(value)
        text(self.label)
        synthetic_url(self.url)


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    title: str
    summary: str
    support_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    strengthen: str
    weaken: str

    def __post_init__(self):
        slug(self.id)
        for value in (self.title, self.summary, self.strengthen, self.weaken):
            text(value)
        for name in ("support_ids", "contradiction_ids"):
            object.__setattr__(self, name, sequence(getattr(self, name), slug))
        object.__setattr__(self, "unknowns", sequence(self.unknowns))
        if not self.support_ids or set(self.support_ids) & set(self.contradiction_ids):
            raise ValueError("Scenarios require unambiguous support references")


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    domain_id: str
    prompt: str
    registered_at: datetime
    deadline: datetime
    review_at: datetime
    resolution_source_id: str
    outcome_rule: str
    invalidation_rule: str
    scenarios: tuple[Scenario, ...]

    def __post_init__(self):
        slug(self.id)
        slug(self.resolution_source_id)
        if self.domain_id not in DOMAIN_IDS:
            raise ValueError("Unsupported question domain")
        for value in (self.prompt, self.outcome_rule, self.invalidation_rule):
            text(value)
        for name in ("registered_at", "deadline", "review_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if not self.registered_at < self.review_at <= self.deadline:
            raise ValueError("Invalid question dates")
        object.__setattr__(self, "scenarios", checked_items(self.scenarios, Scenario))
        if not 1 <= len(self.scenarios) <= 3:
            raise ValueError("One to three scenario drafts are required")


@dataclass(frozen=True, slots=True)
class Reporting:
    mode: str
    registered_at: datetime
    change_window_hours: int
    freshness_hours: int
    format: str

    def __post_init__(self):
        if self.mode != "synthetic" or self.format != "markdown":
            raise ValueError("Only synthetic Markdown reports are supported")
        object.__setattr__(self, "registered_at", utc(self.registered_at))
        for value in (self.change_window_hours, self.freshness_hours):
            if type(value) is not int or not 1 <= value <= 8760:
                raise ValueError("Invalid reporting window")


def checked_items(values, cls):
    if not isinstance(values, (tuple, list)) or not all(type(v) is cls for v in values):
        raise ValueError("Invalid configuration records")
    if len({v.id for v in values}) != len(values):
        raise ValueError("Duplicate configuration identifiers")
    return tuple(values)


@dataclass(frozen=True, slots=True)
class BriefingConfig:
    domains: tuple[Domain, ...]
    sources: tuple[Source, ...]
    questions: tuple[Question, ...]
    reporting: Reporting

    def __post_init__(self):
        for name, cls in (("domains", Domain), ("sources", Source), ("questions", Question)):
            object.__setattr__(self, name, checked_items(getattr(self, name), cls))
        if type(self.reporting) is not Reporting:
            raise ValueError("Invalid reporting configuration")
        if {d.id for d in self.domains} != DOMAIN_IDS:
            raise ValueError("All three domains must be registered")
        if {q.domain_id for q in self.questions} != DOMAIN_IDS:
            raise ValueError("Each domain requires a question")
        source_ids = {s.id for s in self.sources}
        for q in self.questions:
            if q.resolution_source_id not in source_ids:
                raise ValueError("Unknown resolution source")
            if q.registered_at < self.reporting.registered_at:
                raise ValueError("Question predates configuration registration")

    @classmethod
    def from_mapping(cls, raw):
        exact(raw, {"domains", "sources", "questions", "reporting"})
        result = {}
        for name, item in (("domains", Domain), ("sources", Source), ("questions", Question)):
            exact(raw[name], {name})
            if not isinstance(raw[name][name], list):
                raise ValueError("Configuration records must be an array")
            values = []
            for entry in raw[name][name]:
                value = dict(exact(entry, item.__dataclass_fields__))
                if item is Question:
                    if not isinstance(value["scenarios"], list):
                        raise ValueError("Scenarios must be an array")
                    value["scenarios"] = tuple(
                        Scenario(**exact(s, Scenario.__dataclass_fields__))
                        for s in value["scenarios"]
                    )
                values.append(item(**value))
            result[name] = tuple(values)
        result["reporting"] = Reporting(**exact(raw["reporting"], Reporting.__dataclass_fields__))
        return cls(**result)

    @property
    def digest(self):
        return digest(self)


def load_config(directory: Path):
    raw = {}
    for name in ("domains", "sources", "questions", "reporting"):
        with (Path(directory) / f"{name}.toml").open("rb") as stream:
            raw[name] = tomllib.load(stream)
    return BriefingConfig.from_mapping(raw)
