"""Frozen input envelope. Observation times belong to storage, never callers."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from enum import StrEnum


class FieldClass(StrEnum):
    IMMUTABLE = "immutable"
    EDIT_MUTABLE = "edit_mutable"
    UNVERSIONED_MUTABLE = "unversioned_mutable"
    COUNTER = "counter"
    PROVENANCE = "provenance"


class DocumentKind(StrEnum):
    UTTERANCE = "utterance"
    PUBLICATION = "publication"


class Provenance(StrEnum):
    # Real-source provenance is deliberately unavailable in this increment.
    SYNTHETIC = "synthetic"


def utc(value: datetime) -> datetime:
    """Reject ambiguous times; use one representation for ordering and equality."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    return value.astimezone(UTC)


def valid_slug(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) is not None


def valid_hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True, kw_only=True)
class Document:
    doc_hash: str = field(repr=False, metadata={"class": FieldClass.IMMUTABLE})
    kind: DocumentKind = field(metadata={"class": FieldClass.IMMUTABLE})
    source: str = field(metadata={"class": FieldClass.IMMUTABLE})
    published_at: datetime = field(metadata={"class": FieldClass.IMMUTABLE})
    updated_at: datetime = field(metadata={"class": FieldClass.PROVENANCE})
    text: str = field(repr=False, metadata={"class": FieldClass.EDIT_MUTABLE})
    author_hash: str | None = field(repr=False, metadata={"class": FieldClass.IMMUTABLE})
    parent_hash: str | None = field(repr=False, metadata={"class": FieldClass.IMMUTABLE})
    provenance: Provenance = field(metadata={"class": FieldClass.PROVENANCE})

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DocumentKind):
            raise ValueError("Invalid document kind")
        if self.provenance is not Provenance.SYNTHETIC:
            raise ValueError("Only synthetic provenance is supported")
        if not valid_slug(self.source):
            raise ValueError("Invalid source slug")
        if not valid_hash(self.doc_hash):
            raise ValueError("Invalid document hash")
        for value in (self.author_hash, self.parent_hash):
            if value is not None and not valid_hash(value):
                raise ValueError("Invalid identity hash")
        if self.kind is DocumentKind.UTTERANCE and self.author_hash is None:
            raise ValueError("Utterances require a hashed author")
        if self.kind is DocumentKind.PUBLICATION and (
            self.author_hash is not None or self.parent_hash is not None
        ):
            raise ValueError("Publications cannot carry author or parent identities")
        if not isinstance(self.text, str):
            raise ValueError("Text must be a string")
        published, updated = utc(self.published_at), utc(self.updated_at)
        if updated < published:
            raise ValueError("Update time precedes publication")
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "updated_at", updated)

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "Document":
        if not isinstance(values, Mapping) or set(values) != {f.name for f in fields(cls)}:
            raise ValueError("Document fields do not match the contract")
        return cls(**values)
