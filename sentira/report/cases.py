"""Cutoff-bound evidence listing; no automatic procedural or legal resolution."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from sentira.core.cases import EVENT_KINDS, CaseEvent, CaseSnapshot
from sentira.core.document import utc
from sentira.report.briefing import safe


@dataclass(frozen=True, slots=True)
class CaseView:
    cutoff: datetime
    events: tuple[CaseEvent, ...]
    superseded_ids: frozenset[str]
    review_case_ids: frozenset[str]


def case_view(snapshot: CaseSnapshot, cutoff: datetime) -> CaseView:
    cutoff = utc(cutoff)
    visible = tuple(
        sorted(
            (event for event in snapshot.events if event.observed_at <= cutoff),
            key=lambda event: (event.observed_at, event.event_date, event.id),
        )
    )
    return CaseView(
        cutoff,
        visible,
        frozenset(event.supersedes for event in visible if event.supersedes),
        frozenset(event.case_id for event in visible if event.supersedes),
    )


def render_cases(snapshot: CaseSnapshot, *, cutoff: datetime, issued_at: datetime) -> str:
    view = case_view(snapshot, cutoff)
    issued_at = utc(issued_at)
    if issued_at < view.cutoff:
        raise ValueError("Issue time precedes cutoff")
    sources = {source.id: source for source in snapshot.sources}
    labels = dict(snapshot.labels)
    lines = [
        "# SYNTHETIC procedural evidence report",
        "",
        "Fictional, operator-authored snapshot. No verified real-world facts or forecasts.",
        "Source links attribute summaries; the program does not verify their meaning.",
        f"Issued: {issued_at.isoformat()}",
        f"Evidence cutoff: {view.cutoff.isoformat()}",
        "",
        "Gaps mean no evidence in this snapshot, not that an event did not occur.",
        "Elapsed display periods do not establish closure or legal finality.",
        "Snapshot observations are supplied; durable first-observation enforcement is absent.",
        "Omitted documents, later changes and physical completion are not determined.",
    ]
    for case in sorted(snapshot.cases, key=lambda case: case.id):
        events = tuple(event for event in view.events if event.case_id == case.id)
        lines.extend(
            [
                "",
                f"## {case.id}: {safe(case.description)}",
                "",
                f"Location relation: {case.location_relation}",
                f"Location: {safe(case.location)}",
            ]
        )
        if case.id in view.review_case_ids:
            lines.append("REVIEW REQUIRED: supersession recorded; no replacement status inferred.")
        lines.extend(["", "### Evidence dimensions", ""])
        for kind in EVENT_KINDS:
            ids = [event.id for event in events if event.kind == kind]
            status = ", ".join(ids) if ids else "no evidence in this snapshot"
            lines.append(f"- {safe(labels[kind])}: {status}")
        lines.extend(["", "### Records", ""])
        for event in events:
            source = sources[event.source_id]
            url = quote(event.url, safe=":/-._~%") + f"#page={event.page}"
            status = " (SUPERSEDED; retained for review)" if event.id in view.superseded_ids else ""
            lines.extend(
                [
                    f"#### {event.id}{status}",
                    "",
                    f"Kind: {safe(labels[event.kind])}; event date: {event.event_date.isoformat()}",
                    f"Observed: {event.observed_at.isoformat()}; "
                    f"review method: {event.review_method}",
                    f"Institution: {safe(source.institution)}; "
                    f"origin group: {safe(source.origin_group)}",
                    f"Decision reference: {safe(event.decision_reference or 'not supplied')}",
                    f"Published date: {event.published_date or 'not supplied'}",
                    f"Summary: {safe(event.summary)}",
                    f"Source: [{safe(source.label)}, page {event.page}]({url})",
                ]
            )
            if event.supersedes:
                lines.append(f"Supersedes: {event.supersedes}")
            if event.display_start:
                lines.append(f"Stated display start: {event.display_start.isoformat()}")
            if event.duration_days:
                lines.append(f"Stated duration: {event.duration_days} days")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
