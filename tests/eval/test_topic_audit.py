"""Blind, seeded, stratified topic audit with Wilson intervals and agreement."""

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from sentira.eval.topic_audit import (
    AuditItem,
    Candidate,
    audit_metrics,
    cohen_kappa,
    draw_audit,
    wilson,
)

ORIGIN = datetime(2030, 4, 29, tzinfo=UTC)


def candidates():
    rows = []
    for index in range(60):
        stratum = ("positive", "negative", "none")[index % 3]
        published = ORIGIN + timedelta(hours=index - 30)
        assigned = ("economy", "health", None)[index % 3]
        rows.append(Candidate(f"{index:064x}", f"text {index}", published, stratum, assigned))
    return rows


def test_sample_is_seeded_and_stratified():
    first = draw_audit(candidates(), per_stratum=4, seed=7, origin=ORIGIN, mode="development")
    again = draw_audit(candidates(), per_stratum=4, seed=7, origin=ORIGIN, mode="development")
    other = draw_audit(candidates(), per_stratum=4, seed=8, origin=ORIGIN, mode="development")
    assert first == again and first != other

    def chosen(draw):
        return {candidate.doc_hash for candidate in draw[1].values()}

    # Another seed selects other documents, not merely another order.
    assert chosen(first) != chosen(other)
    items, key = first
    strata = sorted(key[item.audit_id].stratum for item in items)
    assert strata == ["negative"] * 4 + ["none"] * 4 + ["positive"] * 4
    small = draw_audit(candidates(), per_stratum=50, seed=7, origin=ORIGIN, mode="development")
    assert len(small[0]) == 30


def test_audit_items_carry_no_timestamp_or_episode_id():
    items, key = draw_audit(candidates(), per_stratum=4, seed=7, origin=ORIGIN, mode="development")
    assert {field.name for field in fields(AuditItem)} == {"audit_id", "text"}
    for item in items:
        candidate = key[item.audit_id]
        assert candidate.doc_hash not in item.audit_id
        assert item.text == candidate.text
    # Items are shuffled across strata, so position reveals nothing either.
    assert [key[item.audit_id].stratum for item in items] != sorted(
        key[item.audit_id].stratum for item in items
    )


def test_development_audit_samples_pre_origin_span_only():
    items, key = draw_audit(candidates(), per_stratum=50, seed=7, origin=ORIGIN, mode="development")
    assert all(key[item.audit_id].published_at < ORIGIN for item in items)
    items, key = draw_audit(
        candidates(), per_stratum=50, seed=7, origin=ORIGIN, mode="confirmatory"
    )
    assert all(key[item.audit_id].published_at >= ORIGIN for item in items)
    with pytest.raises(ValueError):
        draw_audit(candidates(), per_stratum=4, seed=7, origin=ORIGIN, mode="exploratory")
    with pytest.raises(ValueError):
        draw_audit([object()], per_stratum=4, seed=7, origin=ORIGIN, mode="development")


def test_wilson_interval_known_values():
    low, high = wilson(8, 10)
    assert (round(low, 4), round(high, 4)) == (0.4902, 0.9433)
    assert [round(value, 4) for value in wilson(0, 10)] == [0.0, 0.2775]
    assert [round(value, 4) for value in wilson(10, 10)] == [0.7225, 1.0]
    for bad in ((1, 0), (11, 10), (-1, 10)):
        with pytest.raises(ValueError):
            wilson(*bad)


def test_cohen_kappa_known_values():
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "b", "b"]) == 0.5
    assert cohen_kappa(["a", "b"], ["a", "b"]) == 1.0
    # Chance agreement of one leaves kappa undefined.
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None
    with pytest.raises(ValueError):
        cohen_kappa(["a"], ["a", "b"])


def test_audit_metrics_and_recall_floor():
    items, key = draw_audit(candidates(), per_stratum=50, seed=7, origin=ORIGIN, mode="development")
    # The annotator agrees with every assignment except two economy items.
    annotations = {item.audit_id: key[item.audit_id].assigned for item in items}
    economy = [item.audit_id for item in items if key[item.audit_id].assigned == "economy"]
    for audit_id in economy[:2]:
        annotations[audit_id] = None
    metrics = audit_metrics(key, annotations)
    precision, recall = metrics["economy"]
    assert (precision.successes, precision.n) == (len(economy) - 2, len(economy))
    assert (recall.successes, recall.n) == (len(economy) - 2, len(economy) - 2)
    assert metrics["health"][0].successes == metrics["health"][0].n
    with pytest.raises(ValueError):
        audit_metrics(key, {**annotations, "item-extra": None})
