from dataclasses import FrozenInstanceError
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime, timedelta, timezone

import pytest

from sentira.core.document import Document, DocumentKind, FieldClass, Provenance


def test_document_has_no_raw_identifier_or_counter_field():
    assert {f.name for f in dataclass_fields(Document)} == {
        "doc_hash",
        "kind",
        "source",
        "published_at",
        "updated_at",
        "text",
        "author_hash",
        "parent_hash",
        "provenance",
    }


def test_every_field_declares_exactly_one_class():
    assert all(isinstance(f.metadata["class"], FieldClass) for f in dataclass_fields(Document))
    assert all(f.metadata["class"] != FieldClass.COUNTER for f in dataclass_fields(Document))


def test_document_is_frozen(document):
    with pytest.raises(FrozenInstanceError):
        document.text = "replacement"


@pytest.mark.parametrize("extra", ["username", "profile_url", "views", "observed_at", "typo"])
def test_unknown_fields_rejected_without_echoing_values(fields, extra):
    with pytest.raises(ValueError) as exc:
        Document.from_mapping({**fields, extra: "private-marker"})
    assert "private-marker" not in str(exc.value)


@pytest.mark.parametrize(
    "name,value",
    [
        ("published_at", datetime(2026, 1, 1)),
        ("updated_at", "yesterday"),
        ("updated_at", datetime(2025, 1, 1, tzinfo=UTC)),
        ("doc_hash", "raw-identifier"),
        ("author_hash", "raw-identifier"),
        ("parent_hash", "raw-identifier"),
        ("kind", "UTTERANCE"),
        ("source", "https://private.example/account"),
        ("text", 42),
        ("provenance", "live"),
    ],
)
def test_invalid_field_rejected(fields, name, value):
    with pytest.raises(ValueError):
        Document(**{**fields, name: value})


def test_timestamps_normalised_to_utc(fields):
    offset = timezone(timedelta(hours=3))
    doc = Document(**{**fields, "published_at": fields["published_at"].astimezone(offset)})
    assert doc.published_at.tzinfo is UTC
    assert doc.published_at == fields["published_at"]


def test_utterance_requires_author(fields):
    with pytest.raises(ValueError):
        Document(**{**fields, "author_hash": None})


def test_publication_rejects_author_or_parent(fields):
    with pytest.raises(ValueError):
        Document(**{**fields, "kind": DocumentKind.PUBLICATION})
    with pytest.raises(ValueError):
        Document(
            **{
                **fields,
                "kind": DocumentKind.PUBLICATION,
                "author_hash": None,
                "parent_hash": "c" * 64,
            }
        )


def test_publication_without_identity_accepted(fields):
    assert (
        Document(**{**fields, "kind": DocumentKind.PUBLICATION, "author_hash": None}).author_hash
        is None
    )


def test_diagnostics_hide_text_and_hashes(document):
    assert document.text not in repr(document)
    assert document.author_hash not in repr(document)
    assert document.doc_hash not in repr(document)


def test_only_synthetic_provenance_is_available():
    assert list(Provenance) == [Provenance.SYNTHETIC]


def test_from_mapping_requires_complete_contract(fields):
    assert Document.from_mapping(fields) == Document(**fields)
    with pytest.raises(ValueError):
        Document.from_mapping({"text": "private-marker"})
