"""Deterministic rendering of registered drafts, never model-generated forecasts."""

import html
import re
from datetime import timedelta
from urllib.parse import quote

from sentira.core.document import utc


def safe(value):
    value = html.escape(" ".join(str(value).split()), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def render_briefing(config, view, *, issued_at):
    issued_at = utc(issued_at)
    if issued_at < view.cutoff or config.digest != view.config_digest:
        raise ValueError("Issue time or configuration does not match the evidence view")
    rows = {r.evidence.evidence_id: r.evidence for r in view.records}
    fresh_after = view.cutoff - timedelta(hours=config.reporting.freshness_hours)
    recent_after = view.cutoff - timedelta(hours=config.reporting.change_window_hours)
    eligible = {
        key: row
        for key, row in rows.items()
        if row.published_at >= fresh_after and row.evidence_status != "insufficient"
    }
    lines = [
        "# SYNTHETIC scenario briefing",
        "",
        "Fictional fixture only. No forecast probabilities or measured forecasting accuracy.",
        "Scenario drafts are operator-authored; links attribute claims, not verified facts.",
        "",
        f"Issued: {issued_at.isoformat()}",
        f"Evidence cutoff: {view.cutoff.isoformat()}",
        f"Configuration SHA-256: {config.digest}",
        "",
        "## Source coverage",
        "",
        "Coverage describes supplied fixtures, not a successful live collection.",
        "",
    ]
    for source in config.sources:
        own = [row for row in rows.values() if row.source_id == source.id]
        status = (
            "missing"
            if not own
            else "stale"
            if not any(r.published_at >= fresh_after for r in own)
            else "supplied"
        )
        lines.append(f"- {source.id}: {status}")
    for domain in config.domains:
        lines.extend(["", f"## {safe(domain.label)}", ""])
        domain_rows = [r for r in view.records if domain.id in r.evidence.domain_ids]
        changes = [r for r in domain_rows if r.observed_at > recent_after]
        lines.append(f"Newly observed records in change window (calculated): {len(changes)}.")
        if not domain_rows:
            lines.append("Coverage gap: no visible evidence; this does not establish no event.")
        for observed in domain_rows:
            row = observed.evidence
            counter = [key for key in row.contradiction_ids if key in eligible]
            origins = {row.original_source_group} | {
                eligible[key].original_source_group for key in row.support_ids if key in eligible
            }
            status = row.evidence_status
            if status == "corroborated" and len(origins) < 2:
                status = "attributed"
            if counter:
                status = "contested"
            stale = "; stale" if row.published_at < fresh_after else ""
            url = quote(row.source_url, safe=":/%-._~")
            lines.extend(
                [
                    "",
                    f"- **{row.evidence_id}** — {safe(row.claim)}",
                    f"  Attribution: {safe(row.attribution)}; status: {status}{stale}.",
                    f"  [Registered source]({url}); published: {row.published_at.isoformat()};",
                    f"  observed: {observed.observed_at.isoformat()}; expires: "
                    f"{row.expires_at.isoformat()}.",
                    f"  Origin: {row.original_source_group}; rights: {row.rights_record_id};",
                    f"  Content SHA-256: {row.content_digest}.",
                ]
            )
            for label, refs in (
                ("Support", row.support_ids),
                ("Counterevidence", row.contradiction_ids),
            ):
                if refs:
                    available = [key for key in refs if key in eligible]
                    missing = [key for key in refs if key not in eligible]
                    lines.append(f"  {label}: {', '.join(available) or 'none visible'}.")
                    if missing:
                        lines.append(f"  Evidence gap: {', '.join(missing)} unavailable or stale.")
            if row.revision_of:
                lines.append(f"  Revision of: {row.revision_of}; no silent replacement.")
        for question in (q for q in config.questions if q.domain_id == domain.id):
            lines.extend(
                [
                    "",
                    f"### {safe(question.prompt)}",
                    "",
                    f"Question: {question.id}; deadline: {question.deadline.isoformat()};",
                    f"Review: {question.review_at.isoformat()}.",
                    f"Resolution source: {question.resolution_source_id}.",
                    f"Outcome rule: {safe(question.outcome_rule)}",
                    f"Invalidation rule: {safe(question.invalidation_rule)}",
                ]
            )
            if view.cutoff >= question.review_at:
                lines.append("Review due; no automatic outcome resolution has been performed.")
            for scenario in question.scenarios:
                support = [key for key in scenario.support_ids if key in eligible]
                counter = [key for key in scenario.contradiction_ids if key in eligible]
                gaps = [
                    key
                    for key in (*scenario.support_ids, *scenario.contradiction_ids)
                    if key not in eligible
                ]
                lines.append("")
                if len(support) != len(scenario.support_ids):
                    lines.append(
                        f"Insufficient evidence for registered draft {scenario.id}; "
                        "substantive scenario text withheld."
                    )
                else:
                    lines.extend([f"#### {safe(scenario.title)}", "", safe(scenario.summary)])
                lines.extend(
                    [
                        f"Support: {', '.join(support) or 'none visible'}",
                        f"Counterevidence: {', '.join(counter) or 'none visible'}",
                        "Support origins (calculated): "
                        + str(len({eligible[key].original_source_group for key in support})),
                    ]
                )
                if gaps:
                    lines.append(f"Evidence gap: {', '.join(gaps)} unavailable or stale.")
                for unknown in scenario.unknowns:
                    lines.append(f"Unknown: {safe(unknown)}")
                lines.extend(
                    [f"Strengthen: {safe(scenario.strengthen)}", f"Weaken: {safe(scenario.weaken)}"]
                )
    return "\n".join(lines) + "\n"
