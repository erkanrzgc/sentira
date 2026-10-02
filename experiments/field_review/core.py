"""Explicit operator decisions over locked synthetic OCR candidates."""

import hashlib
import html
import json
import re
from pathlib import Path

from experiments.ocr.scoring import verify_lock


def packet_digest(packet: dict) -> str:
    """Bind decisions to canonical UTF-8 JSON, including input byte digests."""
    raw = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_packet(fixtures: Path, results: Path) -> dict:
    """Verify registered inputs and expose candidates without authoring answers."""
    registration = verify_lock(fixtures)
    registration_hash = hashlib.sha256((fixtures / "registration.json").read_bytes()).hexdigest()
    raw = results.read_bytes()
    data = json.loads(raw)
    try:
        if registration["config"]["synthetic"] is not True:
            raise ValueError("Only synthetic registrations are supported")
        if data["synthetic_development_only"] is not True:
            raise ValueError("Only synthetic results are supported")
        if data["registration_sha256"] != registration_hash:
            raise ValueError("Results registration digest mismatch")
        labels = registration["config"]["labels"]
        if not isinstance(labels, dict) or not labels:
            raise ValueError("Configured field labels are required")
        pages = registration["pages"]
        page_ids = [page["id"] for page in pages]
        if len(set(page_ids)) != len(page_ids) or not page_ids:
            raise ValueError("Registered pages must be nonempty and unique")
        rows = [row for row in data["results"] if row["method"] == "ocr"]
        row_ids = [row["page"] for row in rows]
        if len(row_ids) != len(set(row_ids)) or set(row_ids) != set(page_ids):
            raise ValueError("Every registered page must have exactly one OCR row")
        by_page = {row["page"]: row for row in rows}
        fields = []
        for page in pages:
            image = page["png"]
            if image not in registration["files"]:
                raise ValueError("Source image is not a registered file")
            row = by_page[page["id"]]
            if not isinstance(row["fields"], dict) or set(row["fields"]) != set(labels):
                raise ValueError("OCR fields must exactly match configured labels")
            if not isinstance(row["status"], str) or not row["status"]:
                raise ValueError("OCR engine status is required")
            for name in labels:
                observed = row["fields"][name]
                candidate, status = observed["actual"], observed["status"]
                if status not in {"found", "missing", "ambiguous"}:
                    raise ValueError("Unknown candidate status")
                if candidate is not None and not isinstance(candidate, str):
                    raise ValueError("Candidate must be text or null")
                fields.append(
                    {
                        "id": page["id"] + ":" + name,
                        "page_id": page["id"],
                        "field": name,
                        "image": image,
                        "image_sha256": registration["files"][image],
                        "candidate": candidate,
                        "candidate_status": status,
                        "engine_status": row["status"],
                    }
                )
        if len({field["id"] for field in fields}) != len(fields):
            raise ValueError("Field identifiers must be unique")
    except (KeyError, TypeError) as exc:
        raise ValueError("Malformed registration or OCR results") from exc
    return {
        "schema_version": 1,
        "synthetic_development_only": True,
        "registration_sha256": registration_hash,
        "results_sha256": hashlib.sha256(raw).hexdigest(),
        "fields": fields,
    }


def _text(value: object, limit: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(char) < 32 or char in "\x7f\x85\u2028\u2029" for char in value)
    ):
        raise ValueError(f"{label} must be nonempty single-line text of at most {limit} characters")
    return value


def apply_decisions(packet: dict, decisions: dict) -> list[dict]:
    """Apply strict external decisions; omitted fields remain pending gaps."""
    if not isinstance(decisions, dict) or set(decisions) != {"packet_sha256", "reviews"}:
        raise ValueError("Decisions require only packet_sha256 and reviews")
    if decisions["packet_sha256"] != packet_digest(packet):
        raise ValueError("Decision packet digest mismatch")
    if not isinstance(decisions["reviews"], list):
        raise ValueError("Reviews must be a list")
    known = {field["id"]: field for field in packet["fields"]}
    selected = {}
    for review in decisions["reviews"]:
        if not isinstance(review, dict) or not {"field_id", "action"} <= review.keys():
            raise ValueError("Each review requires field_id and action")
        field_id, action = review["field_id"], review["action"]
        if not isinstance(field_id, str) or field_id not in known or field_id in selected:
            raise ValueError("Duplicate or unknown field identifier")
        value, reason = None, ""
        if action == "accept":
            if set(review) != {"field_id", "action"}:
                raise ValueError("Acceptance cannot supply a value or reason")
            field = known[field_id]
            if field["candidate_status"] != "found" or field["engine_status"] != "ok":
                raise ValueError("Only a found candidate from successful OCR can be accepted")
            value = _text(field["candidate"], 200, "Candidate")
            status = "accepted"
        elif action == "correct":
            if set(review) != {"field_id", "action", "value", "reason"}:
                raise ValueError("Correction requires a value and reason")
            value = _text(review["value"], 200, "Correction")
            reason = _text(review["reason"], 500, "Reason")
            status = "corrected"
        elif action == "withhold":
            if set(review) != {"field_id", "action", "reason"}:
                raise ValueError("Withholding requires only a reason")
            reason = _text(review["reason"], 500, "Reason")
            status = "withheld"
        else:
            raise ValueError("Unknown review action")
        selected[field_id] = {"status": status, "value": value, "reason": reason}
    return [
        {
            **{key: field[key] for key in ("id", "page_id", "field", "image", "image_sha256")},
            **selected.get(field["id"], {"status": "pending", "value": None, "reason": ""}),
        }
        for field in packet["fields"]
    ]


def _escape(value: str) -> str:
    # Apostrophes stay literal; "&#x27;" would be broken by the "#" escape below.
    escaped = html.escape(value, quote=False).replace('"', "&quot;")
    escaped = re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped)
    return " ".join(escaped.splitlines())


def render_report(packet: dict, reviewed: list[dict]) -> str:
    """Show only approved values, preserving every source-linked field and gap."""
    if [row["id"] for row in reviewed] != [field["id"] for field in packet["fields"]]:
        raise ValueError("Report must retain every packet field in order")
    lines = [
        "# Synthetic field review",
        "",
        "Development workflow only. Decisions may be simulated; they are not authenticated "
        "human truth or independent reference labels.",
        "",
        f"Packet SHA-256: {packet_digest(packet)}",
        "",
        f"Registration SHA-256: {packet['registration_sha256']}",
        "",
        f"Results SHA-256: {packet['results_sha256']}",
        "",
        "| Page | Field | Status | Approved value or gap | Reason | Source image | Image SHA-256 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for field, row in zip(packet["fields"], reviewed, strict=True):
        status = row["status"]
        if status not in {"pending", "accepted", "corrected", "withheld"}:
            raise ValueError("Unknown reviewed status")
        value = row["value"] if status in {"accepted", "corrected"} else "Gap: " + status
        cells = [
            field["page_id"],
            field["field"],
            status,
            value,
            row["reason"],
            field["image"],
            field["image_sha256"],
        ]
        lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"
