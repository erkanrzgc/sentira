"""Synthetic adversarial checks, not real-world analytical accuracy."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.config.briefing import load_config
from sentira.core.evidence import load_evidence
from sentira.report.briefing import render_briefing
from sentira.storage.evidence import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]
T = datetime(2030, 1, 1, 12, tzinfo=UTC)


def inputs():
    return load_config(ROOT / "config"), load_evidence(ROOT / "examples/synthetic-evidence.toml")


def test_explicit_counterevidence_survives_report():
    config, records = inputs()
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        output = render_briefing(config, ledger.view(config, T), issued_at=T)
    assert "Counterevidence: c2" in output
    assert "status: contested" in output
    assert records[4].claim.rstrip(".") in output


def test_twenty_repetitions_do_not_inflate_support_origins():
    config, records = inputs()
    copies = tuple(replace(records[-1], evidence_id=f"copy-{n}") for n in range(20))
    question = config.questions[-1]
    scenario = replace(question.scenarios[0], support_ids=tuple(r.evidence_id for r in copies))
    config = replace(
        config, questions=(*config.questions[:-1], replace(question, scenarios=(scenario,)))
    )
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, (*records, *copies))
        output = render_briefing(config, ledger.view(config, T), issued_at=T)
    section = output.split("## Regional conflict", 1)[1]
    assert "Support origins (calculated): 1" in section
    assert "Support origins (calculated): 20" not in section


def corrected_reports():
    config, records = inputs()
    now = T
    with EvidenceLedger(":memory:", clock=lambda: now) as ledger:
        ledger.ingest(config, records)
        old = render_briefing(config, ledger.view(config, T), issued_at=T)
        now += timedelta(hours=1)
        correction = replace(
            records[0],
            evidence_id="e2",
            revision_of="e1",
            published_at=now,
            claim="The consultation notice was withdrawn.",
        )
        ledger.ingest(config, (correction,))
        replay = render_briefing(config, ledger.view(config, T), issued_at=T)
        current = render_briefing(config, ledger.view(config, now), issued_at=now)
    return old, replay, current


def test_later_correction_preserves_earlier_report():
    old, replay, current = corrected_reports()
    assert old == replay
    assert "**e2**" not in replay
    assert "**e2**" in current
    assert "Revision of: e1" in current


@pytest.mark.xfail(
    strict=True, reason="Known gap: visible revisions do not gate old scenario support"
)
def test_corrected_support_requires_scenario_review():
    _, _, current = corrected_reports()
    assert "#### The timetable proceeds without a substantive date change" not in current
