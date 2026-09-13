from datetime import timedelta

from sentira.config.schema import load_targets
from sentira.core.document import Document, DocumentKind, Provenance
from sentira.core.identity import IdentifierKind, IdentityHasher
from sentira.storage.asof import AsOfReader
from sentira.storage.repository import Metric, Repository, SnapshotInput


def test_synthetic_boundary_to_strict_read_end_to_end(tmp_path, clock):
    hasher = IdentityHasher(bytes(range(32)))  # Public test key, not a real secret.
    assert load_targets(
        [{"key": "institution-a", "name": "Example institution", "kind": "state_institution"}]
    )
    doc = Document(
        doc_hash=hasher.hash("synthetic", IdentifierKind.COMMENT, "synthetic-comment"),
        author_hash=hasher.hash("synthetic", IdentifierKind.AUTHOR, "synthetic-author"),
        parent_hash=None,
        kind=DocumentKind.UTTERANCE,
        source="synthetic",
        published_at=clock.now - timedelta(hours=1),
        updated_at=clock.now - timedelta(hours=1),
        text="Synthetic feedback about a public service.",
        provenance=Provenance.SYNTHETIC,
    )
    path = tmp_path / "synthetic.sqlite3"
    at = clock.now
    with Repository(path, clock=clock) as repo:
        repo.ingest(doc, snapshots=(SnapshotInput(Metric.LIKES, 1),))
        original = AsOfReader(repo).read(at)
        assert len(original.documents) == 1
        assert original.snapshots[0].value == 1
        clock.advance(hours=1)
        repo.ingest(doc, snapshots=(SnapshotInput(Metric.LIKES, 99),))
    with Repository(path, clock=clock) as repo:
        assert AsOfReader(repo).read(at) == original
        assert AsOfReader(repo).read(clock.now).snapshots[0].value == 99
    stored = path.read_bytes()
    assert b"synthetic-author" not in stored
    assert b"synthetic-comment" not in stored
    assert b"profile_url" not in stored
