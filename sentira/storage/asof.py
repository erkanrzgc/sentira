"""Strict observation-time feature reads; no replay carve-out is implemented."""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from sentira.core.document import Document, DocumentKind, Provenance, utc
from sentira.storage.repository import Metric, Repository, StorageError, timestamp


@dataclass(frozen=True, slots=True)
class VisibleDocument:
    """Internal feature input; excludes observation, edit and provenance metadata."""

    doc_hash: str = field(repr=False)
    kind: DocumentKind
    source: str
    published_at: datetime
    text: str = field(repr=False)
    author_hash: str | None = field(repr=False)
    parent_hash: str | None = field(repr=False)

    @classmethod
    def from_document(cls, doc: Document) -> "VisibleDocument":
        return cls(
            doc.doc_hash,
            doc.kind,
            doc.source,
            doc.published_at,
            doc.text,
            doc.author_hash,
            doc.parent_hash,
        )


@dataclass(frozen=True, slots=True)
class VisibleSnapshot:
    doc_hash: str = field(repr=False)
    metric: Metric
    value: int


@dataclass(frozen=True, slots=True)
class AsOfResult:
    documents: tuple[VisibleDocument, ...]
    snapshots: tuple[VisibleSnapshot, ...]


class VisibilityCursor:
    """The strict observation-time rule for in-memory row streams.

    A row is visible at T exactly when it was observed at or before T, the same
    predicate AsOfReader applies in SQL; an equivalence test keeps them aligned.
    """

    def __init__(self, rows, *, observed_at):
        self._observed_at = observed_at
        self._rows = sorted(rows, key=lambda row: utc(observed_at(row)))
        self._cursor = 0
        self._last = None

    def advance(self, at: datetime):
        """Return the rows that became visible after the previous call, up to `at`."""
        limit = utc(at)
        if self._last is not None and limit < self._last:
            raise ValueError("Visibility time cannot move backwards")
        self._last = limit
        first = self._cursor
        while (
            self._cursor < len(self._rows)
            and utc(self._observed_at(self._rows[self._cursor])) <= limit
        ):
            self._cursor += 1
        return self._rows[first : self._cursor]


class AsOfReader:
    def __init__(self, repository: Repository):
        self._repository = repository

    def read(self, at: datetime) -> AsOfResult:
        limit = timestamp(at)
        db = self._repository._connection()
        try:
            # Both queries share a database snapshot even if another connection writes.
            db.execute("BEGIN")
            rows = db.execute(
                "SELECT * FROM documents WHERE observed_at <= ? AND updated_at <= ? "
                "ORDER BY published_at, doc_hash",
                (limit, limit),
            ).fetchall()
            counters = db.execute(
                "SELECT s.doc_hash, s.metric, s.value FROM snapshots s "
                "JOIN documents d ON d.doc_hash=s.doc_hash "
                "WHERE d.observed_at <= ? AND d.updated_at <= ? AND s.observed_at <= ? "
                "AND s.observed_at=(SELECT MAX(newer.observed_at) FROM snapshots newer "
                "WHERE newer.doc_hash=s.doc_hash AND newer.metric=s.metric "
                "AND newer.observed_at <= ?) ORDER BY s.doc_hash, s.metric",
                (limit, limit, limit, limit),
            ).fetchall()
            documents = []
            for row in rows:
                doc = Document(
                    doc_hash=row["doc_hash"],
                    kind=DocumentKind(row["kind"]),
                    source=row["source"],
                    published_at=datetime.fromisoformat(row["published_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    text=row["text"],
                    author_hash=row["author_hash"],
                    parent_hash=row["parent_hash"],
                    provenance=Provenance(row["provenance"]),
                )
                documents.append(VisibleDocument.from_document(doc))
            result = AsOfResult(
                tuple(documents),
                tuple(
                    VisibleSnapshot(row["doc_hash"], Metric(row["metric"]), row["value"])
                    for row in counters
                ),
            )
            db.commit()
            return result
        except (sqlite3.Error, ValueError):
            db.rollback()
            raise StorageError("Strict read failed") from None
