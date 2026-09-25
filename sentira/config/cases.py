"""Strict, non-executable TOML input for synthetic case snapshots."""

import tomllib
from dataclasses import MISSING, fields
from pathlib import Path

from sentira.core.cases import Case, CaseEvent, CaseSnapshot, CaseSource
from sentira.core.registration import exact


def records(values, cls):
    if not isinstance(values, list):
        raise ValueError("An array of records is required")
    required = [field.name for field in fields(cls) if field.default is MISSING]
    optional = [field.name for field in fields(cls) if field.default is not MISSING]
    return tuple(cls(**exact(value, required, optional)) for value in values)


def parse_cases(values):
    exact(values, ("synthetic", "sources", "cases", "events", "labels"))
    if not isinstance(values["labels"], dict):
        raise ValueError("Reporting labels must be a table")
    return CaseSnapshot(
        sources=records(values["sources"], CaseSource),
        cases=records(values["cases"], Case),
        events=records(values["events"], CaseEvent),
        labels=tuple(values["labels"].items()),
        synthetic=values["synthetic"],
    )


def load_cases(path):
    with Path(path).open("rb") as stream:
        return parse_cases(tomllib.load(stream))
