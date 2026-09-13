"""SQLite schema; counters belong exclusively to observation snapshots."""

from dataclasses import fields
from types import MappingProxyType

from sentira.core.document import Document, FieldClass

COLUMN_CLASSES = MappingProxyType(
    {
        "documents": MappingProxyType(
            {
                **{f.name: f.metadata["class"] for f in fields(Document)},
                "observed_at": FieldClass.PROVENANCE,
            }
        ),
        "snapshots": MappingProxyType(
            {
                "doc_hash": FieldClass.IMMUTABLE,
                "observed_at": FieldClass.PROVENANCE,
                "metric": FieldClass.IMMUTABLE,
                "value": FieldClass.COUNTER,
            }
        ),
        "write_state": MappingProxyType(
            {"singleton": FieldClass.IMMUTABLE, "last_write": FieldClass.PROVENANCE}
        ),
    }
)

DDL = """
CREATE TABLE documents (
    doc_hash TEXT PRIMARY KEY CHECK(length(doc_hash)=64 AND doc_hash NOT GLOB '*[^0-9a-f]*'),
    kind TEXT NOT NULL CHECK(kind IN ('utterance', 'publication')),
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    text TEXT NOT NULL,
    author_hash TEXT CHECK(author_hash IS NULL OR
        (length(author_hash)=64 AND author_hash NOT GLOB '*[^0-9a-f]*')),
    parent_hash TEXT CHECK(parent_hash IS NULL OR
        (length(parent_hash)=64 AND parent_hash NOT GLOB '*[^0-9a-f]*')),
    provenance TEXT NOT NULL CHECK(provenance='synthetic'),
    observed_at TEXT NOT NULL,
    CHECK(updated_at >= published_at),
    CHECK(observed_at >= updated_at),
    CHECK((kind='utterance' AND author_hash IS NOT NULL) OR
          (kind='publication' AND author_hash IS NULL AND parent_hash IS NULL))
) STRICT;
CREATE TABLE snapshots (
    doc_hash TEXT NOT NULL REFERENCES documents(doc_hash),
    observed_at TEXT NOT NULL,
    metric TEXT NOT NULL CHECK(metric IN ('views', 'likes', 'replies', 'comments')),
    value INTEGER NOT NULL CHECK(value >= 0),
    PRIMARY KEY(doc_hash, observed_at, metric)
) STRICT;
CREATE INDEX documents_observed ON documents(observed_at, doc_hash);
CREATE INDEX snapshots_observed ON snapshots(observed_at, doc_hash, metric);
CREATE TABLE write_state (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    last_write TEXT NOT NULL
) STRICT;
"""
