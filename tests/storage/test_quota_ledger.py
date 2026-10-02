"""Storage properties of the quota ledger; synthetic policy and clock only."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.config.quota import load_quota_policy
from sentira.storage.quota import QuotaExhausted, QuotaLedger
from sentira.storage.repository import Repository, StorageError

POLICY = Path(__file__).resolve().parents[2] / "examples/synthetic-quota.toml"
T0 = datetime(2030, 1, 1, 12, tzinfo=UTC)


def policy(tmp_path, retrieval):
    text = POLICY.read_text(encoding="utf-8")
    assert "retrieval = 3000\n" in text and "daily_units = 10000" in text
    text = text.replace("retrieval = 3000\n", f"retrieval = {retrieval}\n")
    text = text.replace("daily_units = 10000", f"daily_units = {7000 + retrieval}")
    path = tmp_path / "quota.toml"
    path.write_text(text, encoding="utf-8")
    return load_quota_policy(path)


def test_two_handles_cannot_overspend_a_reservation(tmp_path):
    path, small = tmp_path / "ledger.sqlite3", policy(tmp_path, 3)
    first = QuotaLedger(path, small, clock=lambda: T0)
    second = QuotaLedger(path, small, clock=lambda: T0)
    with first, second:
        first.debit("retrieval", "videos.list")
        second.debit("retrieval", "videos.list")
        first.debit("retrieval", "videos.list")
        with pytest.raises(QuotaExhausted):
            second.debit("retrieval", "videos.list")
        assert len(second.debits()) == 3


def test_pending_debit_counts_as_spent_after_reopen(tmp_path):
    path, small = tmp_path / "ledger.sqlite3", policy(tmp_path, 1)
    with QuotaLedger(path, small, clock=lambda: T0) as ledger:
        ledger.debit("retrieval", "videos.list")
    # The process stopped between debit and call; the unit stays spent.
    with QuotaLedger(path, small, clock=lambda: T0 + timedelta(minutes=1)) as reopened:
        assert [debit.outcome for debit in reopened.debits()] == ["pending"]
        assert reopened.spent() == {"retrieval": 1}
        with pytest.raises(QuotaExhausted):
            reopened.debit("retrieval", "videos.list")


def test_ledger_refuses_a_foreign_database(tmp_path):
    path = tmp_path / "documents.sqlite3"
    Repository(path).close()
    with pytest.raises(StorageError):
        QuotaLedger(path, policy(tmp_path, 3), clock=lambda: T0)
    with QuotaLedger(tmp_path / "ledger.sqlite3", policy(tmp_path, 3), clock=lambda: T0):
        pass
    with pytest.raises(StorageError):
        Repository(tmp_path / "ledger.sqlite3")


def test_settle_and_inputs_are_validated(tmp_path):
    with QuotaLedger(":memory:", policy(tmp_path, 3), clock=lambda: T0) as ledger:
        with pytest.raises(ValueError, match="Unknown debit"):
            ledger.settle(1, ok=True)
        debit = ledger.debit("retrieval", "videos.list")
        with pytest.raises(ValueError):
            ledger.settle(debit, ok="yes")
        with pytest.raises(ValueError):
            ledger.debit("buffer", "videos.list")
    with pytest.raises(StorageError, match="closed"):
        ledger.debits()
    with pytest.raises(ValueError):
        QuotaLedger(":memory:", object(), clock=lambda: T0)
    with pytest.raises(ValueError, match="aware"):
        QuotaLedger(":memory:", policy(tmp_path, 3), clock=lambda: T0.replace(tzinfo=None))
