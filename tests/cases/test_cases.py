"""Synthetic procedural contracts; no source access or model calls."""

from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path

import pytest


def data():
    return {
        "synthetic": True,
        "sources": [
            {
                "id": "council",
                "label": "Fictional council",
                "institution": "Fictional authority",
                "origin_group": "public-body",
                "url": "https://council.invalid/",
            }
        ],
        "cases": [
            {
                "id": "case-a",
                "description": "Transformer proposal",
                "location": "West of fictional parcel A",
                "location_relation": "adjacent",
            },
            {
                "id": "case-b",
                "description": "Transformer proposal",
                "location": "Fictional area B",
                "location_relation": "affected",
            },
        ],
        "labels": {
            kind: kind.replace("_", " ")
            for kind in (
                "proposal",
                "referral",
                "acceptance",
                "display_notice",
                "display_closure",
                "objection",
                "objection_outcome",
                "amendment",
                "cancellation",
            )
        },
        "events": [event()],
    }


def event(**updates):
    return {
        "id": "event-a",
        "case_id": "case-a",
        "source_id": "council",
        "kind": "acceptance",
        "event_date": date(2030, 1, 1),
        "observed_at": datetime(2030, 1, 2, tzinfo=UTC),
        "url": "https://council.invalid/decision.pdf",
        "page": 2,
        "summary": "A fictional acceptance",
        "review_method": "visual",
        "decision_reference": "decision-1",
        **updates,
    }


def snapshot(values=None):
    from sentira.config.cases import parse_cases

    return parse_cases(data() if values is None else values)


def report(values=None, cutoff=None):
    from sentira.report.cases import render_cases

    cutoff = cutoff or datetime(2030, 2, 1, tzinfo=UTC)
    return render_cases(snapshot(values), cutoff=cutoff, issued_at=cutoff)


def test_same_date_and_topic_do_not_merge_cases():
    values = data()
    values["events"].append(event(id="event-b", case_id="case-b", decision_reference="decision-2"))
    output = report(values)
    assert "case-a" in output and "case-b" in output
    assert "decision-1" in output.replace("\\", "")
    assert "decision-2" in output.replace("\\", "")


def test_adjacent_location_is_not_affected_parcel():
    assert "Location relation: adjacent" in report()


def test_event_date_does_not_backdate_observation():
    assert "A fictional acceptance" not in report(cutoff=datetime(2030, 1, 1, tzinfo=UTC))


def test_invisible_events_do_not_change_report():
    values = data()
    old = report(values)
    values["events"].append(
        event(
            id="later",
            observed_at=datetime(2030, 3, 1, tzinfo=UTC),
            kind="cancellation",
            supersedes="event-a",
        )
    )
    assert report(values) == old


def test_duration_does_not_create_closure():
    values = data()
    values["events"] = [
        event(kind="display_notice", display_start=date(2030, 1, 1), duration_days=30)
    ]
    output = report(values)
    assert "Stated duration: 30 days" in output
    assert "display closure: no evidence in this snapshot" in output


def test_missing_outcome_is_unknown():
    assert "objection outcome: no evidence in this snapshot" in report()


def test_supersession_requires_review_at_cutoff():
    values = data()
    values["events"].append(
        event(
            id="later",
            observed_at=datetime(2030, 3, 1, tzinfo=UTC),
            kind="amendment",
            supersedes="event-a",
        )
    )
    assert "REVIEW REQUIRED" not in report(values)
    output = report(values, datetime(2030, 3, 1, tzinfo=UTC))
    assert "REVIEW REQUIRED" in output and "SUPERSEDED" in output


@pytest.mark.parametrize("change", ["missing", "cross-case", "cycle", "backdated"])
def test_invalid_supersession_rejected(change):
    values = data()
    second = event(id="later", supersedes="event-a")
    if change == "missing":
        second["supersedes"] = "missing"
    elif change == "cross-case":
        second["case_id"] = "case-b"
    elif change == "cycle":
        values["events"][0]["supersedes"] = "later"
    else:
        second["observed_at"] = datetime(2030, 1, 1, tzinfo=UTC)
    values["events"].append(second)
    with pytest.raises(ValueError):
        snapshot(values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("page", 0),
        ("page", True),
        ("page", "2"),
        ("kind", "final"),
        ("owner", "someone"),
        ("observed_at", date(2030, 1, 1)),
        ("observed_at", datetime(2030, 1, 1)),
        ("event_date", "2030-01-01"),
        ("review_method", "model"),
        ("url", "http://council.invalid/a"),
        ("url", "https://real.example/a"),
        ("source_id", "missing"),
        ("duration_days", -1),
        ("display_start", date(2030, 1, 1)),
        ("decision_reference", ""),
        ("summary", []),
    ],
)
def test_case_input_contract_is_strict(field, value):
    values = data()
    values["events"][0][field] = value
    with pytest.raises(ValueError):
        snapshot(values)


@pytest.mark.parametrize("field", ["sources", "cases", "events"])
def test_duplicate_ids_rejected(field):
    values = data()
    values[field].append(deepcopy(values[field][0]))
    with pytest.raises(ValueError):
        snapshot(values)


def test_real_data_declaration_rejected():
    values = data()
    values["synthetic"] = False
    with pytest.raises(ValueError):
        snapshot(values)


def test_case_report_escapes_source_text():
    values = data()
    values["events"][0]["summary"] = "<script>alert(1)</script> [bad](javascript:x)"
    output = report(values)
    assert "<script>" not in output and "[bad](javascript:x)" not in output
    assert "#page=2" in output


def test_case_report_is_deterministic():
    values = data()
    values["events"].append(event(id="event-b", case_id="case-b"))
    expected = report(values)
    values["cases"].reverse()
    values["events"].reverse()
    assert report(values) == expected


def test_source_link_preserves_percent_encoded_path():
    values = data()
    values["events"][0]["url"] = "https://council.invalid/decision%20notice(1).pdf"
    output = report(values)
    assert "https://council.invalid/decision%20notice%281%29.pdf#page=2" in output
    assert "%2520" not in output


def test_issuance_cannot_precede_cutoff():
    from sentira.report.cases import render_cases

    with pytest.raises(ValueError):
        render_cases(
            snapshot(),
            cutoff=datetime(2030, 2, 1, tzinfo=UTC),
            issued_at=datetime(2030, 1, 1, tzinfo=UTC),
        )


def test_shipped_case_fixture_loads():
    from sentira.config.cases import load_cases

    loaded = load_cases(Path("examples/synthetic-cases.toml"))
    assert len(loaded.cases) == 2
