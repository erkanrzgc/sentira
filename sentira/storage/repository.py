"""Atomic writes for synthetic documents. This is not production retention storage."""

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sentira.core.document import Document, utc
from sentira.storage.schema import DDL


class StorageError(RuntimeError):
    """Sanitised operational error; no content or identifiers in messages."""


class Metric(StrEnum):
    VIEWS = "views"
    LIKES = "likes"
    REPLIES = "replies"
    COMMENTS = "comments"


@dataclass(frozen=True, slots=True)
class SnapshotInput:
    metric: Metric
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.metric, Metric):
            raise ValueError("Invalid snapshot metric")
        if type(self.value) is not int or not 0 <= self.value < 2**63:
            raise ValueError("Snapshot count must be a non-negative signed 64-bit integer")


def timestamp(value: datetime) -> str:
    return utc(value).isoformat(timespec="microseconds")


class Repository:
    """Single-threaded local repository; every caller must supply synthetic data.

    Provenance is a validated declaration, not proof of where supplied text came
    from. No source adapter or production ingestion entry point is provided.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], datetime] | None = None):
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._closed = True
        try:
            self._db = sqlite3.connect(path, isolation_level=None)
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA foreign_keys=ON")
            tables = self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if not tables and version == 0:
                self._db.executescript("BEGIN IMMEDIATE;" + DDL + "PRAGMA user_version=1; COMMIT;")
            elif {row[0] for row in tables} != {
                "documents",
                "snapshots",
                "write_state",
            } or version != 1:
                raise StorageError("Unsupported database schema")
            self._closed = False
        except (sqlite3.Error, StorageError):
            if hasattr(self, "_db"):
                self._db.close()
            raise StorageError("Cannot open synthetic storage") from None

    def _connection(self) -> sqlite3.Connection:
        if self._closed:
            raise StorageError("Storage is closed")
        return self._db

    def ingest(self, document: Document, *, snapshots: Iterable[SnapshotInput] = ()) -> None:
        if type(document) is not Document:
            raise ValueError("A validated synthetic document is required")
        values = tuple(snapshots)
        if any(type(value) is not SnapshotInput for value in values):
            raise ValueError("Validated snapshot inputs are required")
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            observed = timestamp(self._clock())
            if observed < timestamp(document.updated_at):
                raise ValueError("Observation precedes document update")
            # Write metadata only; feature reads belong exclusively to asof.py.
            state = db.execute("SELECT last_write FROM write_state WHERE singleton=1").fetchone()
            last = state[0] if state is not None else None
            if last is not None and observed < last:
                raise ValueError("Storage clock regressed")
            db.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(doc_hash) DO NOTHING",
                (
                    document.doc_hash,
                    document.kind.value,
                    document.source,
                    timestamp(document.published_at),
                    timestamp(document.updated_at),
                    document.text,
                    document.author_hash,
                    document.parent_hash,
                    document.provenance.value,
                    observed,
                ),
            )
            db.executemany(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                [
                    (document.doc_hash, observed, value.metric.value, value.value)
                    for value in values
                ],
            )
            db.execute(
                "INSERT INTO write_state VALUES (1, ?) "
                "ON CONFLICT(singleton) DO UPDATE SET last_write=excluded.last_write",
                (observed,),
            )
            db.commit()
        except sqlite3.Error:
            db.rollback()
            raise StorageError("Atomic ingestion failed") from None
        except Exception:
            db.rollback()
            raise

    def close(self) -> None:
        if not self._closed:
            self._db.close()
            self._closed = True

    def __enter__(self) -> "Repository":
        self._connection()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
