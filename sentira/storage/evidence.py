"""Append-only synthetic ledger, separate from the discourse database.

Expiry here is a simulation-time visibility rule, not a deletion implementation.
The clock is storage-owned; the offline CLI explicitly injects a simulation clock.
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sentira.config.briefing import BriefingConfig
from sentira.core.document import utc
from sentira.core.evidence import Evidence
from sentira.core.registration import canonical, digest

TABLES = {"evidence", "registrations", "questions", "ledger_clock"}
DDL = (
    "CREATE TABLE evidence (id TEXT PRIMARY KEY, payload TEXT NOT NULL, "
    "digest TEXT NOT NULL, observed TEXT NOT NULL, published TEXT NOT NULL, "
    "expires TEXT NOT NULL) STRICT",
    "CREATE TABLE registrations (digest TEXT PRIMARY KEY, payload TEXT NOT NULL, "
    "observed TEXT NOT NULL) STRICT",
    "CREATE TABLE questions (id TEXT PRIMARY KEY, digest TEXT NOT NULL) STRICT",
    "CREATE TABLE ledger_clock (id INTEGER PRIMARY KEY CHECK(id=1), "
    "last_write TEXT NOT NULL) STRICT",
)


def stamp(value):
    return utc(value).isoformat(timespec="microseconds")


def decode(payload):
    value = json.loads(payload)
    for field in ("published_at", "expires_at"):
        value[field] = datetime.fromisoformat(value[field])
    return Evidence.from_mapping(value)


@dataclass(frozen=True, slots=True)
class ObservedEvidence:
    evidence: Evidence
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceView:
    config_digest: str
    cutoff: datetime
    records: tuple[ObservedEvidence, ...]


def matches_source(row, sources):
    source = sources.get(row.source_id)
    return (
        source is not None
        and source.origin_group == row.original_source_group
        and source.rights_record_id == row.rights_record_id
        and urlsplit(source.url).netloc == urlsplit(row.source_url).netloc
    )


def validate_references(config, records):
    sources = {s.id: s for s in config.sources}
    for row in records.values():
        if not matches_source(row, sources):
            raise ValueError("Evidence does not match the source registration")
        refs = (*row.support_ids, *row.contradiction_ids)
        if row.revision_of:
            refs += (row.revision_of,)
        for ref in refs:
            other = records.get(ref)
            if other is None or not set(row.domain_ids) <= set(other.domain_ids):
                raise ValueError("Missing or cross-domain evidence reference")
        if row.revision_of and records[row.revision_of].published_at > row.published_at:
            raise ValueError("Revision predates its original")
    # Contradictions can be mutual. Only support/revision dependencies must be acyclic.
    visited, active = set(), set()

    def visit(key):
        if key in active:
            raise ValueError("Cyclic evidence dependency")
        if key in visited:
            return
        active.add(key)
        row = records[key]
        for ref in (*row.support_ids, *((row.revision_of,) if row.revision_of else ())):
            visit(ref)
        active.remove(key)
        visited.add(key)

    for key in records:
        visit(key)
    for question in config.questions:
        for scenario in question.scenarios:
            for ref in (*scenario.support_ids, *scenario.contradiction_ids):
                if ref not in records or question.domain_id not in records[ref].domain_ids:
                    raise ValueError("Unknown or cross-domain scenario evidence")


class EvidenceLedger:
    def __init__(self, path, *, clock: Callable[[], datetime] | None = None):
        self._clock = clock or (lambda: datetime.now(UTC))
        self._db = sqlite3.connect(path, isolation_level=None)
        try:
            self._db.execute("BEGIN IMMEDIATE")
            tables = {
                row[0]
                for row in self._db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if not tables and version == 0:
                for statement in DDL:
                    self._db.execute(statement)
                self._db.execute("PRAGMA user_version=101")
            elif tables != TABLES or version != 101:
                raise ValueError("Not a supported synthetic evidence ledger")
            self._db.execute("COMMIT")
        except Exception:
            self._db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self._db.close()

    def ingest(self, config: BriefingConfig, records):
        if type(config) is not BriefingConfig:
            raise ValueError("A validated configuration is required")
        incoming = tuple(records)
        if any(type(row) is not Evidence for row in incoming):
            raise ValueError("Validated evidence is required")
        if len({row.evidence_id for row in incoming}) != len(incoming):
            raise ValueError("Duplicate evidence identifiers")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            now = utc(self._clock())
            observed = stamp(now)
            previous = self._db.execute("SELECT last_write FROM ledger_clock").fetchone()
            if previous and observed < previous[0]:
                raise ValueError("The storage clock moved backwards")
            if config.reporting.registered_at > now or any(
                q.registered_at > now for q in config.questions
            ):
                raise ValueError("Registration is in the future")
            all_rows = {
                key: decode(payload)
                for key, payload in self._db.execute("SELECT id, payload FROM evidence")
            }
            for row in incoming:
                if row.published_at > now or row.expires_at <= now:
                    raise ValueError("Evidence is not current at observation")
                old = all_rows.get(row.evidence_id)
                if old is not None and old.content_digest != row.content_digest:
                    raise ValueError("An evidence identifier cannot be redefined")
                all_rows[row.evidence_id] = row
            validate_references(config, all_rows)
            for question in config.questions:
                old = self._db.execute(
                    "SELECT digest FROM questions WHERE id=?", (question.id,)
                ).fetchone()
                if old and old[0] != digest(question):
                    raise ValueError("Changed question definitions require a new identifier")
                self._db.execute(
                    "INSERT OR IGNORE INTO questions VALUES (?, ?)", (question.id, digest(question))
                )
            self._db.execute(
                "INSERT OR IGNORE INTO registrations VALUES (?, ?, ?)",
                (config.digest, canonical(config), observed),
            )
            for row in incoming:
                self._db.execute(
                    "INSERT OR IGNORE INTO evidence VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        row.evidence_id,
                        canonical(row),
                        row.content_digest,
                        observed,
                        stamp(row.published_at),
                        stamp(row.expires_at),
                    ),
                )
            self._db.execute(
                "INSERT INTO ledger_clock VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET last_write=excluded.last_write",
                (observed,),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def view(self, config: BriefingConfig, cutoff: datetime) -> EvidenceView:
        at = stamp(cutoff)
        self._db.execute("BEGIN")
        try:
            registration = self._db.execute(
                "SELECT observed FROM registrations WHERE digest=?", (config.digest,)
            ).fetchone()
            if registration is None or registration[0] > at:
                raise ValueError("Configuration was not observed by the cutoff")
            rows = self._db.execute(
                "SELECT payload, observed FROM evidence "
                "WHERE observed<=? AND published<=? AND expires>? ORDER BY id",
                (at, at, at),
            ).fetchall()
            sources = {s.id: s for s in config.sources}
            visible = []
            for payload, observed in rows:
                row = decode(payload)
                if matches_source(row, sources):
                    visible.append(ObservedEvidence(row, datetime.fromisoformat(observed)))
            result = EvidenceView(
                config.digest,
                utc(cutoff),
                tuple(visible),
            )
            self._db.execute("COMMIT")
            return result
        except Exception:
            self._db.execute("ROLLBACK")
            raise
