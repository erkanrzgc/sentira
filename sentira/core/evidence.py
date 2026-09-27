"""Synthetic institutional evidence; observation time is assigned by storage."""

import tomllib
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import DOMAIN_IDS, digest, exact, sequence, slug, synthetic_url, text


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    source_id: str
    domain_ids: tuple[str, ...]
    source_url: str
    published_at: datetime
    claim: str
    attribution: str
    original_source_group: str
    evidence_status: str
    support_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    rights_record_id: str
    expires_at: datetime
    revision_of: str | None = None

    def __post_init__(self):
        for value in (
            self.evidence_id,
            self.source_id,
            self.original_source_group,
            self.rights_record_id,
        ):
            slug(value)
        for name in ("domain_ids", "support_ids", "contradiction_ids"):
            object.__setattr__(self, name, sequence(getattr(self, name), slug))
        if not self.domain_ids or set(self.domain_ids) - DOMAIN_IDS:
            raise ValueError("Invalid evidence domains")
        synthetic_url(self.source_url)
        text(self.claim)
        text(self.attribution)
        for name in ("published_at", "expires_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if self.expires_at <= self.published_at:
            raise ValueError("Expiry must follow publication")
        text(self.evidence_status)
        if self.evidence_status not in {"attributed", "corroborated", "contested", "insufficient"}:
            raise ValueError("Invalid evidence status")
        if self.revision_of is not None:
            slug(self.revision_of)
        if self.evidence_id in (*self.support_ids, *self.contradiction_ids, self.revision_of):
            raise ValueError("Self references are forbidden")
        if set(self.support_ids) & set(self.contradiction_ids):
            raise ValueError("Conflicting reference roles")

    @classmethod
    def from_mapping(cls, value):
        required = set(cls.__dataclass_fields__) - {"revision_of"}
        return cls(**exact(value, required, {"revision_of"}))

    def to_mapping(self):
        return asdict(self)

    @property
    def content_digest(self):
        return digest(self)


def load_evidence(path: Path):
    with Path(path).open("rb") as stream:
        raw = tomllib.load(stream)
    exact(raw, {"mode", "evidence"})
    if raw["mode"] != "synthetic" or not isinstance(raw["evidence"], list):
        raise ValueError("Only synthetic evidence files are supported")
    rows = tuple(Evidence.from_mapping(row) for row in raw["evidence"])
    if len({row.evidence_id for row in rows}) != len(rows):
        raise ValueError("Duplicate evidence identifiers")
    return rows
