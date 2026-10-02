"""Blind, seeded, stratified topic audit with weighted rates, baselines and agreement."""

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from sentira.config.taxonomy import load_taxonomy
from sentira.core.document import DocumentKind
from sentira.eval.topic_audit import (
    AuditItem,
    Candidate,
    audit_metrics,
    cohen_kappa,
    draw_audit,
    wilson,
)
from sentira.nlp.topics import Assignment
from sentira.storage.asof import VisibleDocument

ORIGIN = datetime(2030, 4, 29, tzinfo=UTC)
TAXONOMY = load_taxonomy(Path(__file__).resolve().parents[2] / "examples/synthetic-taxonomy.toml")


def candidate(index, stratum, assigned, published=None):
    published = published or ORIGIN - timedelta(hours=index + 1)
    return Candidate(
        f"{index:064x}", f"text {index}", published, stratum, assigned, TAXONOMY.sha256
    )


def candidates():
    rows = []
    for index in range(60):
        stratum = ("positive", "negative", "none")[index % 3]
        assigned = ("economy", "health", None)[index % 3]
        rows.append(candidate(index, stratum, assigned, ORIGIN + timedelta(hours=index - 30)))
    return rows


def draw(rows=None, taxonomy=TAXONOMY, **overrides):
    options = {"per_stratum": 4, "seed": 7, "origin": ORIGIN, "mode": "development"}
    options.update(overrides)
    rows = candidates() if rows is None else rows
    return draw_audit(rows, taxonomy, expected_sha256=TAXONOMY.sha256, **options)


def chosen(audit):
    return {candidate.doc_hash for candidate in audit.key.values()}


def test_sample_is_seeded_and_stratified():
    first, again, other = draw(), draw(), draw(seed=8)
    assert first == again and first != other
    # Another seed selects other documents, not merely another order.
    assert chosen(first) != chosen(other)
    strata = sorted(first.key[item.audit_id].stratum for item in first.items)
    assert strata == ["negative"] * 4 + ["none"] * 4 + ["positive"] * 4
    # The population of each stratum in the span is recorded for weighting.
    assert dict(first.population) == {"negative": 10, "none": 10, "positive": 10}
    assert dict(first.sampled) == {"negative": 4, "none": 4, "positive": 4}
    assert first.taxonomy_sha256 == TAXONOMY.sha256
    assert first.topics == tuple(topic.id for topic in TAXONOMY.topics)


def test_short_stratum_is_reported_not_hidden():
    audit = draw(per_stratum=50)
    # A stratum smaller than the registered size is taken whole and reported.
    assert len(audit.items) == 30
    assert dict(audit.shortfall) == {"negative": 40, "none": 40, "positive": 40}
    assert dict(draw().shortfall) == {}


def test_audit_items_carry_no_timestamp_or_episode_id():
    audit = draw()
    assert {field.name for field in fields(AuditItem)} == {"audit_id", "text"}
    for item in audit.items:
        candidate = audit.key[item.audit_id]
        assert candidate.doc_hash not in item.audit_id
        assert item.text == candidate.text
    # Items are shuffled across strata, so position reveals nothing either.
    order = [audit.key[item.audit_id].stratum for item in audit.items]
    assert order != sorted(order)


def test_development_audit_samples_pre_origin_span_only():
    audit = draw(per_stratum=50)
    assert all(audit.key[item.audit_id].published_at < ORIGIN for item in audit.items)
    audit = draw(per_stratum=50, mode="confirmatory")
    assert all(audit.key[item.audit_id].published_at >= ORIGIN for item in audit.items)
    with pytest.raises(ValueError):
        draw(mode="exploratory")
    with pytest.raises(ValueError):
        draw([object()])


def test_draw_refuses_duplicates_foreign_digests_and_unknown_topics():
    rows = candidates()
    with pytest.raises(ValueError, match="once"):
        draw([*rows, replace(rows[0], stratum="none")])
    # A copy outside the drawn span is refused as well: the input is inconsistent.
    with pytest.raises(ValueError, match="once"):
        draw([*rows, replace(rows[0], published_at=ORIGIN + timedelta(days=9))])
    with pytest.raises(ValueError, match="another taxonomy"):
        draw([*rows[1:], replace(rows[0], taxonomy_sha256="0" * 64)])
    # Candidates consistent with an unregistered taxonomy are refused too.
    changed = replace(TAXONOMY, version="synthetic-taxonomy-2")
    relabelled = [replace(row, taxonomy_sha256=changed.sha256) for row in rows]
    with pytest.raises(ValueError, match="registered digest"):
        draw(relabelled, taxonomy=changed)
    with pytest.raises(ValueError, match="topic"):
        draw([*rows[1:], replace(rows[0], assigned="econmy")])
    with pytest.raises(ValueError):
        draw(taxonomy=None)


def test_draw_validates_itself():
    audit = draw()
    assert replace(audit) == audit
    first = audit.items[0].audit_id
    foreign = replace(audit.key[first], taxonomy_sha256="0" * 64)
    changed = replace(TAXONOMY, version="synthetic-taxonomy-2")
    for bad in (
        {"key": {**audit.key, first: foreign}},
        {"taxonomy": changed},
        {"population": {"negative": 10, "none": 10}},
        {"population": {**audit.population, "positive": 3}},
        {"items": audit.items[1:]},
        {"items": (replace(audit.items[0], text="other"), *audit.items[1:])},
        {"mode": "exploratory"},
        {"taxonomy": None},
        {"key": list(audit.key.values())},
        {"per_stratum": 0},
    ):
        with pytest.raises(ValueError):
            replace(audit, **bad)
    # A hand-built key cannot hold one document twice.
    same = [i.audit_id for i in audit.items if audit.key[i.audit_id].stratum == "positive"]
    key = {**audit.key, same[1]: audit.key[same[0]]}
    items = tuple(AuditItem(audit_id, candidate.text) for audit_id, candidate in key.items())
    with pytest.raises(ValueError, match="once"):
        replace(audit, key=key, items=items)
    # Topics and digest come from the taxonomy, so neither can be edited apart.
    assert audit.topics == tuple(topic.id for topic in TAXONOMY.topics)
    with pytest.raises(TypeError):
        replace(audit, topics=(*audit.topics, "typo"))


def test_empty_audit_is_refused():
    late = ORIGIN + timedelta(days=365)
    empty = draw(per_stratum=4, origin=late, mode="confirmatory")
    assert empty.items == () and dict(empty.population) == {}
    with pytest.raises(ValueError, match="item"):
        audit_metrics(empty, {})


def test_candidate_carries_the_assignment_digest():
    published = ORIGIN - timedelta(days=1)
    document = VisibleDocument(
        "a" * 64, DocumentKind.UTTERANCE, "synthetic", published, "valtor", None, None
    )
    assignment = Assignment("a" * 64, "economy", TAXONOMY.sha256)
    built = Candidate.from_assignment(assignment, document, stratum="positive")
    assert built == Candidate("a" * 64, "valtor", published, "positive", "economy", TAXONOMY.sha256)
    with pytest.raises(ValueError):
        Candidate.from_assignment(
            replace(assignment, doc_hash="b" * 64), document, stratum="positive"
        )
    title = replace(document, kind=DocumentKind.PUBLICATION)
    with pytest.raises(ValueError):
        Candidate.from_assignment(assignment, title, stratum="positive")
    with pytest.raises(ValueError):
        Candidate.from_assignment(None, document, stratum="positive")
    for bad in ({"doc_hash": "xyz"}, {"taxonomy_sha256": "short"}, {"stratum": "Not A Slug"}):
        with pytest.raises(ValueError):
            replace(built, **bad)


def test_wilson_interval_known_values():
    low, high = wilson(8, 10)
    assert (round(low, 4), round(high, 4)) == (0.4902, 0.9433)
    assert [round(value, 4) for value in wilson(0, 10)] == [0.0, 0.2775]
    assert [round(value, 4) for value in wilson(10, 10)] == [0.7225, 1.0]
    for bad in ((1, 0), (11, 10), (-1, 10)):
        with pytest.raises(ValueError):
            wilson(*bad)


def test_cohen_kappa_known_values():
    first = {"i1": "a", "i2": "a", "i3": "b", "i4": "b"}
    second = {"i1": "a", "i2": "b", "i3": "b", "i4": "b"}
    assert cohen_kappa(first, second) == 0.5
    # Items are paired by identifier, not by position.
    assert cohen_kappa(first, dict(reversed(second.items()))) == 0.5
    # The re-labelled items are a subset of the first labelling.
    assert cohen_kappa({**first, "i5": "c", "i6": "a"}, second) == 0.5
    assert cohen_kappa({"x": "a", "y": "b"}, {"x": "b", "y": "a"}) == -1.0
    assert cohen_kappa({"x": "a", "y": "b"}, {"x": "a", "y": "b"}) == 1.0
    # Chance agreement of one leaves kappa undefined.
    assert cohen_kappa({"x": "a", "y": "a"}, {"x": "a", "y": "a"}) is None
    for bad in (
        (["a", "b"], ["a", "b"]),
        (first, {}),
        (first, {"i9": "a"}),
    ):
        with pytest.raises(ValueError):
            cohen_kappa(*bad)


def test_audit_metrics_and_recall_floor():
    # Every candidate in the span is drawn, so every weight is one.
    audit = draw(per_stratum=50)
    annotations = {item.audit_id: audit.key[item.audit_id].assigned for item in audit.items}
    economy = [
        item.audit_id for item in audit.items if audit.key[item.audit_id].assigned == "economy"
    ]
    # The annotator agrees with every assignment except two economy items.
    for audit_id in economy[:2]:
        annotations[audit_id] = None
    report = audit_metrics(audit, annotations)
    precision, recall = report.topics["economy"].precision, report.topics["economy"].recall
    assert (precision.successes, precision.n) == (len(economy) - 2, len(economy))
    assert (recall.successes, recall.n) == (len(economy) - 2, len(economy) - 2)
    # Equal weights reduce to the plain Wilson interval.
    assert precision.estimate == (len(economy) - 2) / len(economy)
    assert precision.effective_n == len(economy)
    assert (precision.low, precision.high) == wilson(len(economy) - 2, len(economy))
    assert report.topics["health"].precision.estimate == 1.0
    # Accuracy counts an unassigned item as right when it is unlabelled.
    assert (report.accuracy.successes, report.accuracy.n) == (28, 30)
    # A registered topic with no item has no rate rather than a fabricated one.
    assert report.topics["energy"].precision is None and report.topics["energy"].recall is None
    assert report.taxonomy_sha256 == TAXONOMY.sha256
    with pytest.raises(ValueError):
        audit_metrics(audit, {**annotations, "item-extra": None})
    with pytest.raises(ValueError):
        audit_metrics(audit, dict(list(annotations.items())[1:]))
    with pytest.raises(ValueError):
        audit_metrics(None, annotations)
    with pytest.raises(ValueError):
        audit_metrics(audit, list(annotations))


def test_annotation_labels_must_be_registered_topics():
    audit = draw()
    annotations = {item.audit_id: "economy" for item in audit.items}
    assert audit_metrics(audit, annotations).topics["economy"].recall is not None
    first = audit.items[0].audit_id
    for label in ("econmy", "", 3):
        with pytest.raises(ValueError, match="topic"):
            audit_metrics(audit, {**annotations, first: label})


def weighted_world():
    # Few comments are assigned; many topic comments are missed by the lexicon.
    rows = [candidate(index, "assigned", "economy") for index in range(100)]
    rows += [candidate(index, "unassigned", None) for index in range(100, 1100)]
    audit = draw(rows, per_stratum=10)
    annotations = {}
    missed = 0
    for item in audit.items:
        if audit.key[item.audit_id].stratum == "assigned":
            annotations[item.audit_id] = "economy"
        else:
            annotations[item.audit_id] = "economy" if missed < 5 else None
            missed += 1
    return audit, annotations


def test_recall_is_weighted_by_stratum_population():
    audit, annotations = weighted_world()
    report = audit_metrics(audit, annotations)
    recall = report.topics["economy"].recall
    # Ten found in the assigned stratum (weight 10), five missed in the
    # unassigned stratum (weight 100): unweighted 10/15, weighted 100/600.
    assert (recall.successes, recall.n) == (10, 15)
    assert recall.estimate == pytest.approx(1 / 6)
    # Kish effective size: 600 ** 2 / (10 * 10**2 + 5 * 100**2).
    assert recall.effective_n == pytest.approx(360_000 / 51_000)
    assert recall.low < 1 / 6 < recall.high < 2 / 3
    assert report.topics["economy"].precision.estimate == 1.0


def test_accuracy_is_reported_beside_its_baselines():
    audit, annotations = weighted_world()
    report = audit_metrics(audit, annotations)
    prevalence = Fraction(600, 1100)
    assigned = Fraction(100, 1100)
    assert report.topics["economy"].prevalence == pytest.approx(float(prevalence))
    assert report.topics["economy"].assigned_share == pytest.approx(float(assigned))
    # Assigned items are all right; unassigned ones are right when unlabelled.
    assert report.accuracy.estimate == pytest.approx(600 / 1100)
    assert report.majority_label == "economy"
    assert report.majority_baseline == pytest.approx(float(prevalence))
    # A random assigner with the same assigned shares agrees by chance.
    chance = prevalence * assigned + (1 - prevalence) * (1 - assigned)
    assert report.random_baseline == pytest.approx(float(chance))
