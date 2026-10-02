import sqlite3
from dataclasses import replace
from datetime import timedelta, timezone

import pytest

from sentira.storage.asof import AsOfReader, VisibleDocument
from sentira.storage.repository import Metric, Repository, SnapshotInput


def test_visibility_includes_exact_T_but_not_one_microsecond_earlier(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document)
        reader = AsOfReader(repo)
        assert reader.read(clock.now).documents == (VisibleDocument.from_document(document),)
        assert reader.read(clock.now - timedelta(microseconds=1)).documents == ()


def test_snapshot_observed_after_T_never_read(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document, snapshots=(SnapshotInput(Metric.VIEWS, 10),))
        before = clock.now
        clock.advance(hours=1)
        repo.ingest(document, snapshots=(SnapshotInput(Metric.VIEWS, 500),))
        assert AsOfReader(repo).read(before).snapshots[0].value == 10
        assert AsOfReader(repo).read(clock.now).snapshots[0].value == 500


def test_latest_counter_per_metric_kept_separately(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(
            document, snapshots=(SnapshotInput(Metric.VIEWS, 10), SnapshotInput(Metric.LIKES, 2))
        )
        clock.advance(hours=1)
        repo.ingest(document, snapshots=(SnapshotInput(Metric.VIEWS, 11),))
        values = {s.metric: s.value for s in AsOfReader(repo).read(clock.now).snapshots}
        assert values == {Metric.VIEWS: 11, Metric.LIKES: 2}


@pytest.mark.parametrize("future_count", [0, 1, 5, 25])
def test_read_at_T_invariant_to_future_documents_and_snapshots(clock, document, future_count):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document, snapshots=(SnapshotInput(Metric.COMMENTS, 4),))
        at = clock.now
        baseline = AsOfReader(repo).read(at)
        for index in range(future_count):
            clock.advance(hours=1)
            repo.ingest(
                replace(
                    document, doc_hash=f"{index + 100:064x}", text=f"Synthetic later item {index}"
                )
            )
            repo.ingest(document, snapshots=(SnapshotInput(Metric.COMMENTS, index + 20),))
        assert AsOfReader(repo).read(at) == baseline


def test_offset_equivalent_read_times_match(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document)
        assert AsOfReader(repo).read(clock.now) == AsOfReader(repo).read(
            clock.now.astimezone(timezone(timedelta(hours=-5)))
        )


def test_reader_rejects_naive_time(clock):
    with Repository(":memory:", clock=clock) as repo:
        with pytest.raises(ValueError):
            AsOfReader(repo).read(clock.now.replace(tzinfo=None))


def test_results_do_not_expose_observation_metadata_to_features(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(document)
        result = AsOfReader(repo).read(clock.now)
        assert not hasattr(result.documents[0], "observed_at")
        assert not hasattr(result.documents[0], "updated_at")
        assert not hasattr(result.documents[0], "provenance")
        assert isinstance(result.documents, tuple)


def test_mutating_and_deleting_invisible_rows_does_not_change_past(tmp_path, clock, document):
    path = tmp_path / "synthetic.sqlite3"
    with Repository(path, clock=clock) as repo:
        repo.ingest(document)
        at = clock.now
        original = AsOfReader(repo).read(at)
        clock.advance(hours=1)
        repo.ingest(
            replace(document, doc_hash="c" * 64), snapshots=(SnapshotInput(Metric.VIEWS, 10),)
        )
        with sqlite3.connect(path) as connection:
            connection.execute(
                "UPDATE documents SET text='Altered synthetic text' WHERE doc_hash=?", ("c" * 64,)
            )
            connection.execute("UPDATE snapshots SET value=1000 WHERE doc_hash=?", ("c" * 64,))
        assert AsOfReader(repo).read(at) == original
        with sqlite3.connect(path) as connection:
            connection.execute("DELETE FROM snapshots WHERE doc_hash=?", ("c" * 64,))
            connection.execute("DELETE FROM documents WHERE doc_hash=?", ("c" * 64,))
        assert AsOfReader(repo).read(at) == original


def test_cursor_and_reader_agree_on_visibility(document):
    import random

    from sentira.storage.asof import VisibilityCursor

    generator = random.Random(11)
    start = document.published_at
    rows = []
    for index in range(120):
        published = start + timedelta(minutes=generator.randint(0, 3000))
        observed = published + timedelta(minutes=generator.choice((0, 0, 1, 59, 60, 61, 600)))
        rows.append(
            (
                replace(
                    document, doc_hash=f"{index:064x}", published_at=published, updated_at=published
                ),
                observed,
            )
        )
    rows.sort(key=lambda row: row[1])
    now = {"value": rows[0][1]}
    with Repository(":memory:", clock=lambda: now["value"]) as repo:
        for row, observed in rows:
            now["value"] = observed
            repo.ingest(row)
        reader = AsOfReader(repo)
        cursor = VisibilityCursor(rows, observed_at=lambda row: row[1])
        seen = set()
        checkpoints = sorted({observed for _, observed in rows[::7]})
        checkpoints += [checkpoints[-1] + timedelta(hours=1)]
        for at in [start - timedelta(seconds=1), *checkpoints]:
            seen.update(row.doc_hash for row, _ in cursor.advance(at))
            assert seen == {d.doc_hash for d in reader.read(at).documents}
            boundary = at - timedelta(microseconds=1)
            assert {d.doc_hash for d in reader.read(boundary).documents} <= seen
        with pytest.raises(ValueError, match="backwards"):
            cursor.advance(start)
