"""Persistent quota ledger: units are debited before a call is made (BACKTEST B).

A debit draws on the purpose's own reservation for the current quota day, then on
the buffer if the policy lets that purpose overflow, and is refused otherwise. The
reservation check and the debit row are one immediate transaction, so two handles
on the same file cannot both spend the last unit. A failed call stays spent, and a
debit left pending by a crash counts as spent.
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sentira.config.quota import POOLS, PURPOSES, QuotaPolicy
from sentira.storage.repository import StorageError, timestamp

OUTCOMES = ("pending", "ok", "failed")
TABLES = frozenset({"quota_meta", "quota_debits"})


def _in(values):
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


DDL = f"""
CREATE TABLE quota_meta (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    policy_sha256 TEXT NOT NULL
        CHECK(length(policy_sha256)=64 AND policy_sha256 NOT GLOB '*[^0-9a-f]*'),
    last_write TEXT NOT NULL
) STRICT;
CREATE TABLE quota_debits (
    id INTEGER PRIMARY KEY,
    quota_day TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK(purpose IN {_in(PURPOSES)}),
    pool TEXT NOT NULL CHECK(pool IN {_in(POOLS)}),
    endpoint TEXT NOT NULL,
    units INTEGER NOT NULL CHECK(units > 0),
    debited_at TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK(outcome IN {_in(OUTCOMES)}),
    settled_at TEXT,
    CHECK(pool = purpose OR pool = 'buffer'),
    CHECK((outcome = 'pending') = (settled_at IS NULL))
) STRICT;
CREATE INDEX quota_debits_day ON quota_debits(quota_day, pool);
"""


class QuotaExhausted(Exception):  # noqa: N818 - the name states the condition
    """No reservation the purpose may draw on has units left for the quota day."""


@dataclass(frozen=True, slots=True)
class Debit:
    id: int
    quota_day: str
    purpose: str
    pool: str
    endpoint: str
    units: int
    debited_at: datetime
    outcome: str


class QuotaLedger:
    """Single-process ledger for synthetic development; enables no collection."""

    def __init__(
        self,
        path: str | Path,
        policy: QuotaPolicy,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        if type(policy) is not QuotaPolicy:
            raise ValueError("A validated quota policy is required")
        self._policy = policy
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._closed = True
        try:
            self._db = sqlite3.connect(path, isolation_level=None)
        except sqlite3.Error:
            raise StorageError("Cannot open the quota ledger") from None
        try:
            self._open()
        except BaseException:
            self._db.close()
            raise
        self._closed = False

    def _open(self):
        db = self._db
        try:
            db.execute("BEGIN IMMEDIATE")
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if not tables and version == 0:
                created = timestamp(self._clock())
                # Statement by statement: executescript would commit the open transaction.
                for statement in DDL.split(";"):
                    if statement.strip():
                        db.execute(statement)
                db.execute(
                    "INSERT INTO quota_meta VALUES (1, ?, ?)", (self._policy.sha256, created)
                )
                db.execute("PRAGMA user_version=1")
            elif tables != TABLES or version != 1:
                raise StorageError("Unsupported quota ledger schema")
            else:
                row = db.execute(
                    "SELECT policy_sha256 FROM quota_meta WHERE singleton=1"
                ).fetchone()
                if row is None:
                    raise StorageError("Unsupported quota ledger schema")
                if row[0] != self._policy.sha256:
                    raise ValueError("The ledger was created under a different quota policy")
            db.commit()
        except sqlite3.Error:
            db.rollback()
            raise StorageError("Cannot open the quota ledger") from None
        except BaseException:
            db.rollback()
            raise

    def _connection(self):
        if self._closed:
            raise StorageError("The quota ledger is closed")
        return self._db

    def _write(self, operation):
        """Run one write in an immediate transaction after the clock check."""
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            now = self._clock()
            stamp = timestamp(now)
            (last,) = db.execute("SELECT last_write FROM quota_meta WHERE singleton=1").fetchone()
            if stamp < last:
                raise ValueError("The ledger clock moved backwards")
            result = operation(db, now, stamp)
            db.execute("UPDATE quota_meta SET last_write=? WHERE singleton=1", (stamp,))
            db.commit()
            return result
        except sqlite3.Error:
            db.rollback()
            raise StorageError("Quota ledger write failed") from None
        except BaseException:
            db.rollback()
            raise

    def _spent(self, db, day):
        rows = db.execute(
            "SELECT pool, SUM(units) FROM quota_debits WHERE quota_day=? GROUP BY pool", (day,)
        )
        return {pool: total for pool, total in rows if total}

    def debit(self, purpose, endpoint):
        """Record the units of one call before it is made and return the debit id."""
        if purpose not in PURPOSES:
            raise ValueError("Unknown quota purpose")
        cost = self._policy.cost(endpoint)

        def operation(db, now, stamp):
            day = self._policy.quota_day(now)
            spent = self._spent(db, day)
            pools = [purpose]
            if purpose in self._policy.buffer_purposes:
                pools.append("buffer")
            for pool in pools:
                if spent.get(pool, 0) + cost <= self._policy.reservation(pool):
                    break
            else:
                raise QuotaExhausted("The reservation for this purpose is exhausted")
            cursor = db.execute(
                "INSERT INTO quota_debits "
                "(quota_day, purpose, pool, endpoint, units, debited_at, outcome) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                (day, purpose, pool, endpoint, cost, stamp),
            )
            return cursor.lastrowid

        return self._write(operation)

    def settle(self, debit_id, *, ok):
        """Record the outcome of a debited call; the units stay spent either way."""
        if type(debit_id) is not int or type(ok) is not bool:
            raise ValueError("A debit id and a boolean outcome are required")

        def operation(db, now, stamp):
            row = db.execute("SELECT outcome FROM quota_debits WHERE id=?", (debit_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown debit")
            if row[0] != "pending":
                raise ValueError("The debit is already settled")
            db.execute(
                "UPDATE quota_debits SET outcome=?, settled_at=? WHERE id=?",
                ("ok" if ok else "failed", stamp, debit_id),
            )

        self._write(operation)

    def debits(self):
        rows = self._connection().execute(
            "SELECT id, quota_day, purpose, pool, endpoint, units, debited_at, outcome "
            "FROM quota_debits ORDER BY id"
        )
        return tuple(
            Debit(*row[:6], datetime.fromisoformat(row[6]), row[7]) for row in rows.fetchall()
        )

    def spent(self):
        """Units spent per pool on the current quota day, pending and failed included."""
        return self._spent(self._connection(), self._policy.quota_day(self._clock()))

    def close(self) -> None:
        if not self._closed:
            self._db.close()
            self._closed = True

    def __enter__(self) -> "QuotaLedger":
        self._connection()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
