"""Offline eligibility for explicitly reviewed synthetic field candidates."""

import re
from datetime import date, datetime

from experiments.field_review.core import _escape, apply_decisions, packet_digest

FIELDS = {"decision", "date", "scale", "duration"}


def _timestamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Invalid timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identifiers must be nonempty text")
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 digest")
    return value


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("Malformed object keys")


def _list(value):
    if not isinstance(value, list):
        raise ValueError("Expected a list")
    return value


def _valid(field, value):
    if not isinstance(value, str):
        return False
    if field == "decision":
        return re.fullmatch(r"[0-9]+(?:[./-][0-9]+)+", value) is not None
    if field == "date":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if field == "scale":
        return bool(re.fullmatch(r"1/[0-9]+", value) and any(c != "0" for c in value[2:]))
    if field == "duration":
        return value == "one calendar month" or bool(
            re.fullmatch(r"[0-9]+ days", value) and any(c != "0" for c in value[:-5])
        )
    return False


def evaluate(packet: dict, decisions: dict, context: dict, cutoff: datetime) -> dict:
    """Recompute decisions and expose values only while their binding is current."""
    try:
        return _evaluate(packet, decisions, context, cutoff)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Malformed eligibility inputs") from exc


def _evaluate(packet, decisions, context, cutoff):
    cutoff = _timestamp(cutoff)
    if not isinstance(packet, dict) or packet.get("synthetic_development_only") is not True:
        raise ValueError("Only synthetic packets are supported")
    fields = _list(packet["fields"])
    if not fields:
        raise ValueError("Packet fields must not be empty")
    pages, identifiers = {}, set()
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Malformed packet field")
        identifier, page = _text(field["id"]), _text(field["page_id"])
        _text(field["field"])
        _text(field["image"])
        digest = _digest(field["image_sha256"])
        if identifier in identifiers or (page in pages and pages[page] != digest):
            raise ValueError("Duplicate field or inconsistent page image")
        identifiers.add(identifier)
        pages[page] = digest
    _keys(
        context,
        "synthetic packet_sha256 decisions_sha256 reviewed_at permitted_fields bindings versions",
    )
    if context["synthetic"] is not True:
        raise ValueError("Only synthetic contexts are supported")
    packet_hash, decision_hash = packet_digest(packet), packet_digest(decisions)
    if context["packet_sha256"] != packet_hash or context["decisions_sha256"] != decision_hash:
        raise ValueError("Context digest mismatch")
    reviewed_at = _timestamp(context["reviewed_at"])
    permitted = _list(context["permitted_fields"])
    if any(not isinstance(name, str) or name not in FIELDS for name in permitted):
        raise ValueError("Unknown permitted field")
    if len(set(permitted)) != len(permitted):
        raise ValueError("Duplicate permitted field")
    versions, timelines = {}, {page: [] for page in pages}
    for version in _list(context["versions"]):
        _keys(version, "id page_id observed_at image_sha256 status")
        identifier, page = _text(version["id"]), _text(version["page_id"])
        observed = _timestamp(version["observed_at"])
        _digest(version["image_sha256"])
        status = version["status"]
        if not isinstance(status, str) or status not in {"available", "unavailable", "withdrawn"}:
            raise ValueError("Unknown source status")
        if identifier in versions or page not in pages:
            raise ValueError("Duplicate version or foreign page")
        if any(row["observed_at"] == observed for row in timelines[page]):
            raise ValueError("Page observations must have distinct timestamps")
        normalised = {**version, "observed_at": observed}
        versions[identifier] = normalised
        timelines[page].append(normalised)
    for timeline in timelines.values():
        timeline.sort(key=lambda row: row["observed_at"])
    bindings = {}
    for binding in _list(context["bindings"]):
        _keys(binding, "page_id version_id")
        page, identifier = _text(binding["page_id"]), _text(binding["version_id"])
        if page not in pages or page in bindings or identifier not in versions:
            raise ValueError("Unknown or duplicate binding")
        bound = versions[identifier]
        visible = [row for row in timelines[page] if row["observed_at"] <= reviewed_at]
        if (
            not visible
            or visible[-1]["id"] != identifier
            or bound["page_id"] != page
            or bound["status"] != "available"
            or bound["image_sha256"] != pages[page]
        ):
            raise ValueError("Binding must match the latest available source at review")
        bindings[page] = identifier
    if set(bindings) != set(pages):
        raise ValueError("Every packet page requires exactly one binding")
    reviewed = apply_decisions(packet, decisions)
    rows = []
    for row in reviewed:
        visible = [v for v in timelines[row["page_id"]] if v["observed_at"] <= cutoff]
        latest = visible[-1] if visible else None
        if reviewed_at > cutoff:
            status = "review_not_visible"
        elif latest is None:
            status = "source_unavailable"
        elif latest["status"] != "available":
            status = "source_" + latest["status"]
        elif latest["id"] != bindings[row["page_id"]]:
            status = "review_required"
        elif row["status"] in {"pending", "withheld"}:
            status = row["status"]
        elif row["field"] not in permitted:
            status = "not_permitted"
        elif not _valid(row["field"], row["value"]):
            status = "invalid_value"
        else:
            status = "eligible_candidate"
        rows.append(
            {
                **{key: row[key] for key in ("id", "field", "page_id")},
                "reviewed_source_version_id": bindings[row["page_id"]],
                "reviewed_image_sha256": row["image_sha256"],
                "latest_source_version_id": latest["id"] if latest else None,
                "latest_image_sha256": latest["image_sha256"] if latest else None,
                "status": status,
                "value": row["value"] if status == "eligible_candidate" else None,
            }
        )
    return {
        "schema_version": 1,
        "synthetic_development_only": True,
        "packet_sha256": packet_hash,
        "decisions_sha256": decision_hash,
        "reviewed_at": reviewed_at.isoformat(),
        "cutoff": cutoff.isoformat(),
        "fields": rows,
    }


def render_report(result: dict) -> str:
    """Render candidate values and explicit gaps without adding event semantics."""
    lines = [
        "# Synthetic reviewed-field eligibility",
        "",
        "Candidates only; no event date, legal effect or authenticity is established. "
        "Observation and review times are operator-authored simulation data.",
        "",
        f"Cutoff: {_escape(result['cutoff'])}",
        "",
        f"Packet SHA-256: {result['packet_sha256']}",
        "",
        f"Decisions SHA-256: {result['decisions_sha256']}",
        "",
        "| Page | Field | Reviewed version | Reviewed image SHA-256 | Latest visible version | "
        "Latest visible image SHA-256 | Status | Candidate or gap |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in result["fields"]:
        value = row["value"] if row["status"] == "eligible_candidate" else "Gap: " + row["status"]
        cells = [
            row["page_id"],
            row["field"],
            row["reviewed_source_version_id"],
            row["reviewed_image_sha256"],
            row["latest_source_version_id"] or "None",
            row["latest_image_sha256"] or "None",
            row["status"],
            value,
        ]
        lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"
