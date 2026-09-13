from dataclasses import replace
from datetime import datetime

import pytest

from sentira.storage.asof import AsOfReader, VisibleDocument
from sentira.storage.repository import Metric, Repository, SnapshotInput, StorageError


def test_observed_at_cannot_be_supplied_by_caller(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        with pytest.raises(TypeError):
            repo.ingest(document, observed_at=document.published_at)
        repo.ingest(document)
        assert AsOfReader(repo).read(clock.now).documents == (
            VisibleDocument.from_document(document),
        )
        assert AsOfReader(repo).read(document.published_at).documents == ()


def test_first_observation_wins_on_reingest(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document)
        first = clock.now
        clock.advance(hours=1)
        repo.ingest(replace(document, text="Later replacement"))
        assert AsOfReader(repo).read(first).documents == (VisibleDocument.from_document(document),)
        assert AsOfReader(repo).read(clock.now).documents == (
            VisibleDocument.from_document(document),
        )


def test_failed_write_rolls_back_document_and_snapshots(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        # Same document, observation and metric cannot be written twice.
        with pytest.raises(StorageError):
            repo.ingest(
                document, snapshots=(SnapshotInput(Metric.LIKES, 1), SnapshotInput(Metric.LIKES, 2))
            )
        result = AsOfReader(repo).read(clock.now)
        assert result.documents == ()
        assert result.snapshots == ()
        repo.ingest(document, snapshots=(SnapshotInput(Metric.LIKES, 3),))
        assert AsOfReader(repo).read(clock.now).snapshots[0].value == 3


def test_rollback_preserves_previous_data(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document, snapshots=(SnapshotInput(Metric.VIEWS, 4),))
        before = AsOfReader(repo).read(clock.now)
        clock.advance(hours=1)
        with pytest.raises(StorageError):
            repo.ingest(
                replace(document, doc_hash="c" * 64),
                snapshots=(SnapshotInput(Metric.LIKES, 1), SnapshotInput(Metric.LIKES, 2)),
            )
        assert AsOfReader(repo).read(clock.now) == before


def test_database_persists_and_clock_floor_survives_reopen(tmp_path, clock, document):
    path = tmp_path / "synthetic.sqlite3"
    with Repository(path, clock=clock) as repo:
        repo.ingest(document)
    with Repository(path, clock=clock) as repo:
        assert AsOfReader(repo).read(clock.now).documents == (
            VisibleDocument.from_document(document),
        )
        clock.advance(hours=-1)
        with pytest.raises(ValueError):
            repo.ingest(replace(document, doc_hash="c" * 64))


@pytest.mark.parametrize("value", [-1, True, 1.5, 2**63, "2"])
def test_invalid_snapshot_value_rejected(value):
    with pytest.raises(ValueError):
        SnapshotInput(Metric.LIKES, value)


def test_invalid_snapshot_metric_rejected():
    with pytest.raises(ValueError):
        SnapshotInput("arbitrary-counter", 1)


def test_naive_storage_clock_rejected(document):
    with Repository(":memory:", clock=lambda: datetime(2026, 1, 2)) as repo:
        with pytest.raises(ValueError):
            repo.ingest(document)


def test_document_cannot_be_observed_before_its_update(clock, document):
    clock.advance(hours=-3)
    with Repository(":memory:", clock=clock) as repo:
        with pytest.raises(ValueError):
            repo.ingest(document)


def test_ingest_rejects_unvalidated_input(clock):
    with Repository(":memory:", clock=clock) as repo:
        with pytest.raises(ValueError) as exc:
            repo.ingest({"text": "private-marker"})
        assert "private-marker" not in str(exc.value)


def test_storage_errors_do_not_include_document_content(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        with pytest.raises(StorageError) as exc:
            repo.ingest(
                document, snapshots=(SnapshotInput(Metric.VIEWS, 1), SnapshotInput(Metric.VIEWS, 1))
            )
        assert document.text not in str(exc.value)
        assert document.doc_hash not in str(exc.value)


def test_closed_repository_fails_cleanly(clock, document):
    repo = Repository(":memory:", clock=clock)
    repo.close()
    repo.close()
    with pytest.raises(StorageError):
        repo.ingest(document)


def test_duplicate_ingestion_advances_clock_floor_across_reopen(tmp_path, clock, document):
    path = tmp_path / "synthetic.sqlite3"
    with Repository(path, clock=clock) as repo:
        repo.ingest(document)
        clock.advance(hours=3)
        repo.ingest(document)
    clock.advance(hours=-1)
    with Repository(path, clock=clock) as repo:
        with pytest.raises(ValueError, match="clock regressed"):
            repo.ingest(replace(document, doc_hash="c" * 64))


def test_failed_ingestion_does_not_advance_clock_floor(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document)
        clock.advance(hours=3)
        with pytest.raises(StorageError):
            repo.ingest(
                document, snapshots=(SnapshotInput(Metric.LIKES, 1), SnapshotInput(Metric.LIKES, 2))
            )
        clock.advance(hours=-1)
        repo.ingest(replace(document, doc_hash="c" * 64))
        assert len(AsOfReader(repo).read(clock.now).documents) == 2
