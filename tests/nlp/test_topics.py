"""Single-label lexical topic assignment on as-of comment text only."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from sentira.config.taxonomy import load_taxonomy
from sentira.core.document import DocumentKind
from sentira.nlp.topics import assign, assign_visible
from sentira.storage.asof import AsOfReader
from sentira.storage.repository import Repository

TAXONOMY = load_taxonomy(Path(__file__).resolve().parents[2] / "examples/synthetic-taxonomy.toml")


def test_single_label_priority_rule_deterministic():
    # Most distinct keywords wins; a repeated keyword counts once.
    assert assign("valtor prensek sentavo", TAXONOMY) == "economy"
    assert assign("valtor sentavo kirumel", TAXONOMY) == "health"
    assert assign("prensek prensek prensek sentavo kirumel", TAXONOMY) == "health"
    # A tie goes to the topic registered first.
    assert assign("sentavo prensek", TAXONOMY) == "economy"
    assert assign("mardeck anselm", TAXONOMY) == "social-security"
    assert assign("nothing relevant here", TAXONOMY) is None
    assert assign("sentavo prensek", TAXONOMY) == assign("prensek sentavo", TAXONOMY)
    with pytest.raises(ValueError):
        assign("valtor", None)
    with pytest.raises(ValueError):
        assign_visible(None, TAXONOMY, expected_sha256=TAXONOMY.sha256)


def test_case_map_and_prefix_matching():
    # The registered case map folds before lower-casing.
    assert assign("KASTOR", TAXONOMY) == "local-services"
    # A stem matches the start of a word; a whole word matches only itself.
    assert assign("valtoruna", TAXONOMY) == "economy"
    assert assign("xvaltor", TAXONOMY) is None
    assert assign("prenseks", TAXONOMY) is None
    assert assign("Prensek, again!", TAXONOMY) == "economy"


def test_uses_frozen_taxonomy_hash(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(replace(document, text="valtor prensek"))
        result = AsOfReader(repo).read(clock.now)
    (assignment,) = assign_visible(result, TAXONOMY, expected_sha256=TAXONOMY.sha256)
    assert (assignment.topic, assignment.taxonomy_sha256) == ("economy", TAXONOMY.sha256)
    changed = replace(TAXONOMY, version="synthetic-taxonomy-2")
    with pytest.raises(ValueError, match="digest"):
        assign_visible(result, changed, expected_sha256=TAXONOMY.sha256)


def test_assignment_reads_only_as_of_text(clock, document):
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(replace(document, text="valtor"))
        at = clock.now
        clock.advance(hours=2)
        # A comment edited after T is absent from every topic at T.
        edited = replace(
            document,
            doc_hash="c" * 64,
            text="sentavo kirumel",
            updated_at=document.published_at + timedelta(hours=3),
        )
        clock.advance(hours=2)
        repo.ingest(edited)
        before = assign_visible(
            AsOfReader(repo).read(at), TAXONOMY, expected_sha256=TAXONOMY.sha256
        )
        after = assign_visible(
            AsOfReader(repo).read(clock.now), TAXONOMY, expected_sha256=TAXONOMY.sha256
        )
    assert [item.topic for item in before] == ["economy"]
    assert sorted(item.topic for item in after) == ["economy", "health"]


def test_video_title_not_used_for_assignment(clock, document):
    title = replace(
        document,
        doc_hash="d" * 64,
        kind=DocumentKind.PUBLICATION,
        author_hash=None,
        text="valtor prensek dumari",
    )
    with Repository(":memory:", clock=clock) as repo:
        repo.ingest(title)
        repo.ingest(replace(document, text="sentavo"))
        result = AsOfReader(repo).read(clock.now)
    assignments = assign_visible(result, TAXONOMY, expected_sha256=TAXONOMY.sha256)
    assert [(item.doc_hash, item.topic) for item in assignments] == [(document.doc_hash, "health")]
