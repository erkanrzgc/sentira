"""Synthetic candidate eligibility and temporal boundaries."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from experiments.eligibility.core import evaluate, render_report
from experiments.field_review.core import packet_digest


def time(day):
    return datetime(2026, 1, day, tzinfo=UTC)


@pytest.fixture
def inputs():
    packet = {
        "synthetic_development_only": True,
        "fields": [
            {
                "id": "p:" + name,
                "page_id": "p",
                "field": name,
                "image": "p.png",
                "image_sha256": "a" * 64,
                "candidate": value,
                "candidate_status": "found",
                "engine_status": "ok",
            }
            for name, value in {
                "decision": "001/02-3",
                "date": "2024-02-29",
                "scale": "1/0500",
                "duration": "one calendar month",
            }.items()
        ],
    }
    decisions = {
        "packet_sha256": packet_digest(packet),
        "reviews": [{"field_id": row["id"], "action": "accept"} for row in packet["fields"]],
    }
    context = {
        "synthetic": True,
        "packet_sha256": packet_digest(packet),
        "decisions_sha256": packet_digest(decisions),
        "reviewed_at": time(2),
        "permitted_fields": ["decision", "date", "scale", "duration"],
        "bindings": [{"page_id": "p", "version_id": "v1"}],
        "versions": [
            {
                "id": "v1",
                "page_id": "p",
                "observed_at": time(1),
                "image_sha256": "a" * 64,
                "status": "available",
            }
        ],
    }
    return packet, decisions, context


def test_valid_candidates_preserve_all_characters_and_json_timestamps(inputs):
    result = evaluate(*inputs, time(2))
    assert [row["value"] for row in result["fields"]] == [
        "001/02-3",
        "2024-02-29",
        "1/0500",
        "one calendar month",
    ]
    assert all(row["status"] == "eligible_candidate" for row in result["fields"])
    assert result["cutoff"] == time(2).isoformat()
    assert r"eligible\_candidate" in render_report(result)
    assert "event_date" not in result


def test_future_observation_invariance_and_changed_then_reverted_requires_review(inputs):
    before = evaluate(*inputs, time(2))
    versions = inputs[2]["versions"]
    for day, digest in [(3, "b"), (4, "a")]:
        versions.append(
            {**versions[0], "id": f"v{day}", "observed_at": time(day), "image_sha256": digest * 64}
        )
    assert evaluate(*inputs, time(2)) == before
    for day in (3, 4):
        assert all(
            row["status"] == "review_required" and row["value"] is None
            for row in evaluate(*inputs, time(day))["fields"]
        )
    row = evaluate(*inputs, time(3))["fields"][0]
    assert (row["reviewed_source_version_id"], row["reviewed_image_sha256"]) == ("v1", "a" * 64)
    assert (row["latest_source_version_id"], row["latest_image_sha256"]) == ("v3", "b" * 64)


@pytest.mark.parametrize("status", ["unavailable", "withdrawn"])
def test_source_status_suppresses_values(inputs, status):
    inputs[2]["versions"].append(
        {**inputs[2]["versions"][0], "id": "v2", "observed_at": time(3), "status": status}
    )
    assert all(
        row["status"] == "source_" + status and row["value"] is None
        for row in evaluate(*inputs, time(3))["fields"]
    )


def test_pre_review_is_invisible_and_pending_withheld_not_permitted_remain_gaps(inputs):
    assert all(
        row["status"] == "review_not_visible" and row["value"] is None
        for row in evaluate(*inputs, time(1))["fields"]
    )
    packet, decisions, context = inputs
    decisions["reviews"] = [
        {"field_id": "p:date", "action": "withhold", "reason": "gap"},
        {"field_id": "p:scale", "action": "accept"},
    ]
    context["decisions_sha256"] = packet_digest(decisions)
    context["permitted_fields"] = ["date"]
    assert [row["status"] for row in evaluate(*inputs, time(2))["fields"]] == [
        "pending",
        "withheld",
        "not_permitted",
        "pending",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("date", "2025-02-29"),
        ("date", "2024-2-29"),
        ("date", "2024-02-29 "),
        ("decision", "123"),
        ("decision", "12//3"),
        ("scale", "1/000"),
        ("scale", "1/5.5"),
        ("duration", "0 days"),
        ("duration", "1 month"),
        ("duration", "-1 days"),
        ("duration", "one calendar month "),
    ],
)
def test_invalid_values_are_not_repaired(inputs, field, value):
    packet, decisions, context = inputs
    decisions["reviews"] = [
        {
            "field_id": "p:" + field,
            "action": "correct",
            "value": value,
            "reason": "Synthetic inspection",
        }
    ]
    context["decisions_sha256"] = packet_digest(decisions)
    row = next(row for row in evaluate(*inputs, time(2))["fields"] if row["field"] == field)
    assert row["status"] == "invalid_value" and row["value"] is None
    assert value not in render_report(evaluate(*inputs, time(2)))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c.update(synthetic=1),
        lambda c: c.update(extra=True),
        lambda c: c.update(packet_sha256="b" * 64),
        lambda c: c.update(decisions_sha256="b" * 64),
        lambda c: c.update(reviewed_at=datetime(2026, 1, 2)),
        lambda c: c.update(permitted_fields="date"),
        lambda c: c.update(permitted_fields=[[]]),
        lambda c: c.update(permitted_fields=["date", "date"]),
        lambda c: c.update(permitted_fields=["event_date"]),
        lambda c: c.update(bindings=[]),
        lambda c: c.update(bindings=[None]),
        lambda c: c["bindings"][0].update(version_id="unknown"),
        lambda c: c["bindings"][0].update(page_id="foreign"),
        lambda c: c["versions"][0].update(image_sha256="b" * 64),
        lambda c: c["versions"][0].update(status="withdrawn"),
        lambda c: c["versions"][0].update(status=[]),
        lambda c: c["versions"][0].update(page_id="foreign"),
        lambda c: c["versions"][0].update(observed_at="2026-01-01"),
        lambda c: c["versions"].append(deepcopy(c["versions"][0])),
        lambda c: c["versions"].append({**c["versions"][0], "id": "same-time"}),
        lambda c: c["versions"].append({**c["versions"][0], "id": "newer", "observed_at": time(2)}),
    ],
)
def test_malformed_context_and_wrong_binding_raise_value_error(inputs, mutation):
    mutation(inputs[2])
    with pytest.raises(ValueError):
        evaluate(*inputs, time(3))


@pytest.mark.parametrize(
    "slot,value", [(0, None), (0, {"fields": []}), (1, None), (2, []), (3, "2026-01-02")]
)
def test_malformed_runtime_inputs_fail_with_value_error(inputs, slot, value):
    args = [*inputs, time(2)]
    args[slot] = value
    with pytest.raises(ValueError):
        evaluate(*args)
