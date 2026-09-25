"""Immutable synthetic procedural records, independent of scenario domains."""

from dataclasses import dataclass
from datetime import date, datetime

from sentira.core.document import utc
from sentira.core.registration import slug, synthetic_url, text

EVENT_KINDS = (
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


def calendar_date(value):
    if type(value) is not date:
        raise ValueError("A calendar date is required")
    return value


def positive_integer(value):
    if type(value) is not int or value < 1:
        raise ValueError("A positive integer is required")


@dataclass(frozen=True, slots=True)
class CaseSource:
    id: str
    label: str
    institution: str
    origin_group: str
    url: str

    def __post_init__(self):
        slug(self.id)
        slug(self.origin_group)
        text(self.label)
        text(self.institution)
        synthetic_url(self.url)


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    description: str
    location: str
    location_relation: str

    def __post_init__(self):
        slug(self.id)
        text(self.description)
        text(self.location)
        if self.location_relation not in ("adjacent", "affected"):
            raise ValueError("A location relation is required")


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseEvent:
    id: str
    case_id: str
    source_id: str
    kind: str
    event_date: date
    observed_at: datetime
    url: str
    page: int
    summary: str
    review_method: str
    decision_reference: str | None = None
    published_date: date | None = None
    display_start: date | None = None
    duration_days: int | None = None
    supersedes: str | None = None

    def __post_init__(self):
        for value in (self.id, self.case_id, self.source_id):
            slug(value)
        if self.kind not in EVENT_KINDS or self.review_method not in ("text", "visual"):
            raise ValueError("Unsupported event kind or review method")
        calendar_date(self.event_date)
        object.__setattr__(self, "observed_at", utc(self.observed_at))
        synthetic_url(self.url)
        positive_integer(self.page)
        text(self.summary)
        if self.decision_reference is not None:
            text(self.decision_reference)
        if self.kind == "acceptance" and self.decision_reference is None:
            raise ValueError("Acceptance requires a decision reference")
        if self.published_date is not None:
            calendar_date(self.published_date)
            if self.published_date > self.observed_at.date():
                raise ValueError("Publication cannot follow observation")
        if self.display_start is not None or self.duration_days is not None:
            if self.kind != "display_notice":
                raise ValueError("Display fields belong to a display notice")
            if self.display_start is not None:
                calendar_date(self.display_start)
            if self.duration_days is not None:
                positive_integer(self.duration_days)
        if self.supersedes is not None:
            slug(self.supersedes)


def unique_index(records):
    result = {record.id: record for record in records}
    if len(result) != len(records):
        raise ValueError("Duplicate record IDs")
    return result


@dataclass(frozen=True, slots=True)
class CaseSnapshot:
    sources: tuple[CaseSource, ...]
    cases: tuple[Case, ...]
    events: tuple[CaseEvent, ...]
    labels: tuple[tuple[str, str], ...]
    synthetic: bool

    def __post_init__(self):
        if self.synthetic is not True:
            raise ValueError("Only explicitly synthetic snapshots are supported")
        for name, cls in (("sources", CaseSource), ("cases", Case), ("events", CaseEvent)):
            records = getattr(self, name)
            if not isinstance(records, (tuple, list)) or any(
                not isinstance(record, cls) for record in records
            ):
                raise ValueError("Invalid record collection")
            object.__setattr__(self, name, tuple(records))
        sources, cases, events = (
            unique_index(rows) for rows in (self.sources, self.cases, self.events)
        )
        if not sources or not cases:
            raise ValueError("Sources and cases are required")
        labels = tuple(tuple(pair) for pair in self.labels)
        if (
            any(len(pair) != 2 for pair in labels)
            or len(labels) != len(EVENT_KINDS)
            or {pair[0] for pair in labels} != set(EVENT_KINDS)
        ):
            raise ValueError("Every event kind requires exactly one reporting label")
        for _, label in labels:
            text(label)
        object.__setattr__(self, "labels", labels)
        for event in self.events:
            if event.case_id not in cases or event.source_id not in sources:
                raise ValueError("Unknown case or source reference")
            seen = {event.id}
            cursor = event
            while cursor.supersedes is not None:
                target = events.get(cursor.supersedes)
                if target is None or target.case_id != event.case_id or target.id in seen:
                    raise ValueError("Invalid supersession graph")
                if target.observed_at > cursor.observed_at:
                    raise ValueError("A revision cannot precede its target observation")
                seen.add(target.id)
                cursor = target
