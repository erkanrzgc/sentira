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


def test_case_report_renders_apostrophe_verbatim():
    values = data()
    values["events"][0]["summary"] = "The authority's notice"
    output = report(values)
    assert "&#x27;" not in output and "&\\#x27;" not in output
    assert "The authority's notice" in output


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


def test_calendar_month_wording_is_preserved_without_day_conversion():
    values = data()
    values["events"] = [
        event(
            kind="display_notice",
            display_start=date(2030, 1, 31),
            summary="Display is announced for one calendar month.",
        )
    ]
    output = report(values, datetime(2030, 5, 1, tzinfo=UTC))
    assert "one calendar month" in output
    assert "Stated duration:" not in output
    assert "display closure: no evidence in this snapshot" in output


def test_observation_at_cutoff_is_visible_but_one_microsecond_later_is_not():
    values = data()
    boundary = datetime(2030, 1, 2, tzinfo=UTC)
    values["events"].append(
        event(id="after", observed_at=boundary.replace(microsecond=1), summary="Later content")
    )
    output = report(values, boundary)
    assert "A fictional acceptance" in output
    assert "Later content" not in output


def test_equivalent_timezone_observations_produce_identical_output():
    values = data()
    expected = report(values)
    values["events"][0]["observed_at"] = datetime.fromisoformat("2030-01-02T03:00:00+03:00")
    assert report(values) == expected


def test_notice_can_announce_a_future_display_without_implying_completion():
    values = data()
    values["events"] = [
        event(
            kind="display_notice",
            event_date=date(2030, 4, 1),
            display_start=date(2030, 4, 1),
            duration_days=20,
        )
    ]
    output = report(values)
    assert "Stated display start: 2030-04-01" in output
    assert "display closure: no evidence in this snapshot" in output


def test_transitive_supersession_keeps_all_records_and_old_cutoff():
    values = data()
    old_report = report(values, datetime(2030, 1, 2, tzinfo=UTC))
    values["events"].extend(
        [
            event(
                id="revision-a",
                kind="amendment",
                supersedes="event-a",
                observed_at=datetime(2030, 1, 3, tzinfo=UTC),
            ),
            event(
                id="revision-b",
                kind="amendment",
                supersedes="revision-a",
                observed_at=datetime(2030, 1, 4, tzinfo=UTC),
            ),
        ]
    )
    assert report(values, datetime(2030, 1, 2, tzinfo=UTC)) == old_report
    output = report(values)
    assert "#### event-a (SUPERSEDED" in output
    assert "#### revision-a (SUPERSEDED" in output
    assert "#### revision-b\n" in output
    assert output.count("REVIEW REQUIRED") == 1


def test_competing_revisions_are_retained_without_choosing_a_winner():
    values = data()
    values["events"].extend(
        [
            event(
                id="revision-a",
                kind="amendment",
                supersedes="event-a",
                summary="Competing account A",
            ),
            event(
                id="revision-b",
                kind="cancellation",
                supersedes="event-a",
                summary="Competing account B",
            ),
        ]
    )
    output = report(values)
    assert "Competing account A" in output and "Competing account B" in output
    assert "REVIEW REQUIRED" in output
    assert "no replacement status inferred" in output


def test_empty_event_snapshot_does_not_invent_an_outcome():
    values = data()
    values["events"] = []
    output = report(values)
    assert output.count("acceptance: no evidence in this snapshot") == 2
    assert output.count("objection outcome: no evidence in this snapshot") == 2
    assert "REVIEW REQUIRED" not in output


@pytest.mark.parametrize("field", ["sources", "cases", "events", "labels"])
def test_invalid_top_level_collections_rejected(field):
    values = data()
    values[field] = 42
    with pytest.raises(ValueError):
        snapshot(values)


def test_future_publication_is_not_accepted_as_already_observed():
    values = data()
    values["events"][0]["published_date"] = date(2030, 1, 3)
    with pytest.raises(ValueError):
        snapshot(values)


def test_publication_date_is_separate_from_event_date():
    values = data()
    values["events"][0]["event_date"] = date(2029, 12, 1)
    values["events"][0]["published_date"] = date(2030, 1, 1)
    output = report(values)
    assert "event date: 2029-12-01" in output
    assert "Published date: 2030-01-01" in output
    assert "Observed: 2030-01-02" in output
