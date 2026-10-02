"""Synthetic-only source-linked review contracts."""

import hashlib
import json

import pytest

from experiments.field_review.core import (
    apply_decisions,
    build_packet,
    packet_digest,
    render_report,
)


@pytest.fixture
def inputs(tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"synthetic page bytes")
    registration = {
        "config": {"synthetic": True, "labels": {"date": "Date", "scale": "Scale"}},
        "pages": [{"id": "page", "png": "page.png"}],
        "files": {"page.png": hashlib.sha256(image.read_bytes()).hexdigest()},
    }
    raw = json.dumps(registration).encode()
    (tmp_path / "registration.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / "registration.sha256").write_text(digest)
    results = {
        "registration_sha256": digest,
        "synthetic_development_only": True,
        "results": [
            {"method": "pdf_text"},
            {
                "method": "ocr",
                "page": "page",
                "status": "ok",
                "fields": {
                    "date": {
                        "actual": "WRONG-CANDIDATE",
                        "status": "found",
                        "expected": "SECRET-ANSWER",
                    },
                    "scale": {"actual": None, "status": "missing", "expected": "SECRET"},
                },
                "baselines": {"majority": "SECRET-BASELINE"},
            },
        ],
    }
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results))
    return tmp_path, path


def decisions(packet, *reviews):
    return {"packet_sha256": packet_digest(packet), "reviews": list(reviews)}


def test_packet_excludes_answers_and_pending_report_suppresses_candidates(inputs):
    packet = build_packet(*inputs)
    assert len(packet["fields"]) == 2
    assert "SECRET" not in json.dumps(packet)
    reviewed = apply_decisions(packet, decisions(packet))
    assert all(row["status"] == "pending" and row["value"] is None for row in reviewed)
    report = render_report(packet, reviewed)
    assert "WRONG-CANDIDATE" not in report
    assert "gap" in report.lower()
    assert packet_digest(packet) in report
    assert packet["fields"][0]["image_sha256"] in report


def test_explicit_correction_never_uses_expected_and_retains_omissions(inputs):
    packet = build_packet(*inputs)
    rows = apply_decisions(
        packet,
        decisions(
            packet,
            {
                "field_id": "page:date",
                "action": "correct",
                "value": "Operator value",
                "reason": "Simulated inspection",
            },
        ),
    )
    assert rows[0]["value"] == "Operator value"
    assert rows[1]["status"] == "pending"
    assert "Operator value" in render_report(packet, rows)


@pytest.mark.parametrize(
    "status,engine", [("missing", "ok"), ("ambiguous", "ok"), ("found", "failed")]
)
def test_unusable_candidate_cannot_be_accepted(inputs, status, engine):
    packet = build_packet(*inputs)
    packet["fields"][0].update(candidate_status=status, engine_status=engine)
    with pytest.raises(ValueError):
        apply_decisions(packet, decisions(packet, {"field_id": "page:date", "action": "accept"}))


@pytest.mark.parametrize(
    "reviews",
    [
        [{"field_id": "unknown", "action": "accept"}],
        [{"field_id": "page:date", "action": "accept"}] * 2,
        [{"field_id": "page:date", "action": "accept", "value": "extra"}],
        [{"field_id": "page:date", "action": "correct", "value": "new"}],
        [{"field_id": "page:date", "action": "withhold", "reason": " "}],
        [{"field_id": "page:date", "action": "withhold", "reason": "why", "value": "bad"}],
        [{"field_id": "page:date", "action": "correct", "reason": "why", "value": "a\nb"}],
    ],
)
def test_malformed_or_duplicate_decisions_fail(inputs, reviews):
    packet = build_packet(*inputs)
    with pytest.raises(ValueError):
        apply_decisions(packet, decisions(packet, *reviews))


def test_digest_binding_covers_results_and_packet(inputs):
    packet = build_packet(*inputs)
    review = decisions(packet)
    inputs[1].write_text(inputs[1].read_text() + "\n")
    changed = build_packet(*inputs)
    with pytest.raises(ValueError):
        apply_decisions(changed, review)


def test_tampered_source_is_rejected(inputs):
    (inputs[0] / "page.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_packet(*inputs)


@pytest.mark.parametrize("change", ["duplicate", "missing", "unknown", "field", "hash", "real"])
def test_result_integrity_is_required(inputs, change):
    data = json.loads(inputs[1].read_text())
    if change == "duplicate":
        data["results"].append(data["results"][1])
    elif change == "missing":
        data["results"].pop()
    elif change == "unknown":
        data["results"][1]["page"] = "other"
    elif change == "field":
        del data["results"][1]["fields"]["scale"]
    elif change == "hash":
        data["registration_sha256"] = "bad"
    else:
        data["synthetic_development_only"] = False
    inputs[1].write_text(json.dumps(data))
    with pytest.raises(ValueError):
        build_packet(*inputs)


def test_report_escapes_reviewed_text_and_withholds_value(inputs):
    packet = build_packet(*inputs)
    rows = apply_decisions(
        packet,
        decisions(
            packet,
            {
                "field_id": "page:date",
                "action": "correct",
                "value": "<script>|[x](url)",
                "reason": "Simulated",
            },
            {"field_id": "page:scale", "action": "withhold", "reason": "Unreadable"},
        ),
    )
    report = render_report(packet, rows)
    assert "<script>" not in report
    assert "[x](url)" not in report
    assert rows[1]["value"] is None
    assert "withheld" in report


def test_report_renders_apostrophe_verbatim(inputs):
    packet = build_packet(*inputs)
    rows = apply_decisions(
        packet,
        decisions(
            packet,
            {"field_id": "page:scale", "action": "withhold", "reason": "Clerk's stamp covers it"},
        ),
    )
    report = render_report(packet, rows)
    assert "&#x27;" not in report and "&\\#x27;" not in report
    assert "Clerk's stamp covers it" in report


@pytest.mark.parametrize(
    "key,value", [("action", []), ("field_id", {}), ("reason", []), ("value", {}), ("extra", True)]
)
def test_malformed_decision_types_fail_cleanly(inputs, key, value):
    packet = build_packet(*inputs)
    review = {"field_id": "page:date", "action": "correct", "value": "new", "reason": "why"}
    review[key] = value
    with pytest.raises(ValueError):
        apply_decisions(packet, decisions(packet, review))


@pytest.mark.parametrize("data", [[], None, {"results": None}])
def test_malformed_results_fail_cleanly(inputs, data):
    inputs[1].write_text(json.dumps(data))
    with pytest.raises(ValueError):
        build_packet(*inputs)


def test_accept_preserves_candidate_only_after_explicit_decision(inputs):
    packet = build_packet(*inputs)
    rows = apply_decisions(packet, decisions(packet, {"field_id": "page:date", "action": "accept"}))
    assert rows[0]["status"] == "accepted"
    assert rows[0]["value"] == "WRONG-CANDIDATE"
    assert "WRONG" in render_report(packet, rows)


@pytest.mark.parametrize("candidate", [None, "", " "])
def test_empty_found_candidate_cannot_be_accepted(inputs, candidate):
    packet = build_packet(*inputs)
    packet["fields"][0]["candidate"] = candidate
    with pytest.raises(ValueError):
        apply_decisions(packet, decisions(packet, {"field_id": "page:date", "action": "accept"}))


@pytest.mark.parametrize(
    "key,value", [("value", "x" * 201), ("reason", "x" * 501), ("value", "x\u2028y")]
)
def test_correction_limits_are_enforced(inputs, key, value):
    packet = build_packet(*inputs)
    review = {"field_id": "page:date", "action": "correct", "value": "new", "reason": "why"}
    review[key] = value
    with pytest.raises(ValueError):
        apply_decisions(packet, decisions(packet, review))


def test_packet_digest_is_canonical_and_detects_candidate_changes(inputs):
    packet = build_packet(*inputs)
    assert packet_digest(packet) == packet_digest(dict(reversed(list(packet.items()))))
    digest = packet_digest(packet)
    packet["fields"][0]["candidate"] = "changed"
    assert packet_digest(packet) != digest


@pytest.mark.parametrize("change", ["unregistered", "real"])
def test_registration_requires_registered_image_and_synthetic_flag(inputs, change):
    path = inputs[0] / "registration.json"
    data = json.loads(path.read_text())
    if change == "unregistered":
        data["files"] = {}
    else:
        data["config"]["synthetic"] = False
    raw = json.dumps(data).encode()
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (inputs[0] / "registration.sha256").write_text(digest)
    results = json.loads(inputs[1].read_text())
    results["registration_sha256"] = digest
    inputs[1].write_text(json.dumps(results))
    with pytest.raises(ValueError):
        build_packet(*inputs)
