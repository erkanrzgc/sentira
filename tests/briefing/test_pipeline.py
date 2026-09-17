"""Synthetic briefing contracts: no source or model calls."""

import copy
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentira.config.briefing import BriefingConfig, load_config
from sentira.core.evidence import Evidence, load_evidence
from sentira.report.briefing import render_briefing
from sentira.storage.evidence import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]
T = datetime(2030, 1, 1, 12, tzinfo=UTC)


@pytest.fixture
def config():
    return load_config(ROOT / "config")


@pytest.fixture
def records():
    return load_evidence(ROOT / "examples/synthetic-evidence.toml")


def report(config, records, *, cutoff=T):
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        return render_briefing(config, ledger.view(config, cutoff), issued_at=cutoff)


def test_three_domains_share_briefing_pipeline(config, records):
    output = report(config, records)
    for label in ("Elections", "Government policy", "Regional conflict"):
        assert f"## {label}" in output
    assert "Strengthen:" in output and "Weaken:" in output
    assert "2030-01-08" in output


def test_briefing_is_deterministic(config, records):
    assert report(config, records) == report(config, tuple(reversed(records)))
    assert config.digest in report(config, records)


def test_briefing_ignores_future_evidence(config, records):
    now = T
    with EvidenceLedger(":memory:", clock=lambda: now) as ledger:
        ledger.ingest(config, records)
        before = render_briefing(config, ledger.view(config, T), issued_at=T)
        now += timedelta(days=1)
        extra = records[0].to_mapping()
        extra.update(evidence_id="later", claim="Future secret", published_at=now)
        ledger.ingest(config, (Evidence.from_mapping(extra),))
        assert render_briefing(config, ledger.view(config, T), issued_at=T) == before


def test_unknown_evidence_reference_rejected(config, records):
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        with pytest.raises(ValueError):
            ledger.ingest(config, records[:-1])
        with pytest.raises(ValueError):
            ledger.view(config, T)


def test_syndicated_claims_share_one_origin(config, records):
    output = report(config, records)
    assert "Support origins (calculated): 1" in output
    assert "Support: c1, c3" in output


def test_gaps_and_counterevidence_are_reported(config, records):
    output = report(config, records)
    assert "survey: missing" in output
    assert "Counterevidence: c2" in output
    assert "Counterevidence: p2" in output
    assert "Unknown:" in output


def test_synthetic_briefing_has_no_forecast_probability(config, records):
    output = report(config, records)
    assert "SYNTHETIC" in output
    assert "No forecast probabilities" in output
    assert "%" not in output


def test_briefing_runs_offline(config, records):
    # The autouse socket guard fails any attempted network access.
    assert report(config, records)


def raw_config():
    return {
        name: tomllib.loads((ROOT / f"config/{name}.toml").read_text("utf-8"))
        for name in ("domains", "sources", "questions", "reporting")
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x["reporting"].update(api_key="hidden"),
        lambda x: x["reporting"].update(mode="live"),
        lambda x: x["reporting"].update(freshness_hours=True),
        lambda x: x["questions"]["questions"][0].update(domain_id="person"),
        lambda x: x["questions"]["questions"][0].update(resolution_source_id="unknown"),
        lambda x: x["questions"]["questions"][0].update(review_at=T.replace(tzinfo=None)),
        lambda x: x["questions"]["questions"][0]["scenarios"][0].update(probability=0.9),
        lambda x: x["sources"]["sources"].append(copy.deepcopy(x["sources"]["sources"][0])),
        lambda x: x["sources"]["sources"][0].update(url="https://secret@site.invalid/"),
        lambda x: x["sources"]["sources"][0].update(url="https://example.com/"),
    ],
)
def test_invalid_briefing_config_rejected(mutation):
    raw = raw_config()
    mutation(raw)
    with pytest.raises(ValueError):
        BriefingConfig.from_mapping(raw)


def test_config_digest_ignores_formatting_but_tracks_definition(config):
    raw = raw_config()
    raw["questions"]["questions"][0]["prompt"] += " Revised"
    assert BriefingConfig.from_mapping(raw).digest != config.digest
    assert BriefingConfig.from_mapping(raw_config()).digest == config.digest


@pytest.mark.parametrize(
    "change",
    [
        {"observed_at": T},
        {"author_id": "private"},
        {"likes": 3},
        {"source_url": "https://site.com/"},
        {"published_at": T.replace(tzinfo=None)},
        {"expires_at": T - timedelta(days=3)},
        {"evidence_status": "certain"},
        {"domain_ids": ["person"]},
        {"support_ids": ["e1"]},
    ],
)
def test_invalid_evidence_rejected(records, change):
    row = records[0].to_mapping()
    row.update(change)
    with pytest.raises(ValueError):
        Evidence.from_mapping(row)


def test_question_definition_cannot_change_under_same_id(config, records):
    raw = raw_config()
    raw["questions"]["questions"][0]["prompt"] += " Changed"
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        with pytest.raises(ValueError):
            ledger.ingest(BriefingConfig.from_mapping(raw), records)
        assert ledger.view(config, T).records


def test_changed_evidence_id_is_rejected(config, records):
    row = records[0].to_mapping()
    row["claim"] = "Changed"
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        with pytest.raises(ValueError):
            ledger.ingest(config, (Evidence.from_mapping(row),))


def test_future_observation_and_expiry_withhold_scenarios(config, records):
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        # Registration itself was not observed before T: no fabricated past report.
        with pytest.raises(ValueError):
            ledger.view(config, T - timedelta(microseconds=1))
        output = render_briefing(
            config, ledger.view(config, T + timedelta(days=32)), issued_at=T + timedelta(days=32)
        )
        assert "Insufficient evidence" in output
        assert "The timetable proceeds" not in output
        assert "survey: missing" in output


def test_duplicate_clock_watermark_survives_reopen(tmp_path, config, records):
    path = tmp_path / "ledger.db"
    with EvidenceLedger(path, clock=lambda: T) as ledger:
        ledger.ingest(config, records)
    with EvidenceLedger(path, clock=lambda: T + timedelta(days=1)) as ledger:
        ledger.ingest(config, records)
    with EvidenceLedger(path, clock=lambda: T + timedelta(hours=1)) as ledger:
        with pytest.raises(ValueError):
            ledger.ingest(config, records)
        assert len(ledger.view(config, T).records) == 6


def test_unsafe_markdown_is_escaped(config, records):
    row = records[0].to_mapping()
    row["claim"] = "<script>alert(1)</script> ![tracking](https://evil.invalid/)\n# Heading"
    output = report(config, (Evidence.from_mapping(row), *records[1:]))
    assert "<script>" not in output
    assert "![tracking]" not in output
    assert "\n# Heading" not in output


def test_issue_before_cutoff_rejected(config, records):
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        with pytest.raises(ValueError):
            render_briefing(config, ledger.view(config, T), issued_at=T - timedelta(seconds=1))


@pytest.mark.parametrize(
    "change",
    [
        {"source_id": "unknown"},
        {"original_source_group": "invented"},
        {"rights_record_id": "unregistered"},
        {"support_ids": ("p1",)},
        {"revision_of": "missing"},
        {"source_url": "https://other.invalid/"},
        {"published_at": T + timedelta(seconds=1)},
    ],
)
def test_failed_batch_leaves_no_registration(config, records, change):
    row = records[0].to_mapping()
    row.update(change)
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        with pytest.raises(ValueError):
            ledger.ingest(config, (Evidence.from_mapping(row), *records[1:]))
        with pytest.raises(ValueError):
            ledger.view(config, T)
        ledger.ingest(config, records)
        assert len(ledger.view(config, T).records) == 6


def test_cyclic_support_rejected(config, records):
    row = records[3].to_mapping()
    row["support_ids"] = ("c3",)  # c3 already depends on c1.
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        with pytest.raises(ValueError, match="Cyclic"):
            ledger.ingest(config, (*records[:3], Evidence.from_mapping(row), *records[4:]))


def test_revision_is_append_only(config, records):
    row = records[0].to_mapping()
    row.update(evidence_id="e2", revision_of="e1", claim="Revised fixture")
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, (*records, Evidence.from_mapping(row)))
        output = render_briefing(config, ledger.view(config, T), issued_at=T)
        assert "Revision of: e1" in output
        assert "Support: e1" not in output
        assert "Review required" in output


def test_repetition_cannot_self_certify_corroboration(config, records):
    row = records[-1].to_mapping()
    row["evidence_status"] = "corroborated"
    output = report(config, (*records[:-1], Evidence.from_mapping(row)))
    assert "status: corroborated" not in output


def test_expired_support_does_not_corroborate(config, records):
    first, second = records[3].to_mapping(), records[4].to_mapping()
    first.update(evidence_status="corroborated", support_ids=("c2",), contradiction_ids=())
    second["expires_at"] = T + timedelta(seconds=1)
    altered = (
        *records[:3],
        Evidence.from_mapping(first),
        Evidence.from_mapping(second),
        records[5],
    )
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, altered)
        assert "status: corroborated" in render_briefing(
            config, ledger.view(config, T), issued_at=T
        )
        later = T + timedelta(seconds=1)
        output = render_briefing(config, ledger.view(config, later), issued_at=later)
        assert "status: corroborated" not in output
        assert "c2 unavailable or stale" in output


def test_wrong_database_is_not_modified(tmp_path):
    from sentira.storage.repository import Repository

    path = tmp_path / "discourse.db"
    with Repository(path):
        pass
    before = path.read_bytes()
    with pytest.raises(ValueError):
        EvidenceLedger(path)
    assert path.read_bytes() == before


def test_view_excludes_sources_outside_selected_registration(config, records):
    raw = raw_config()
    raw["sources"]["sources"].append(
        {
            "id": "new-source",
            "label": "New fixture source",
            "url": "https://new.invalid/",
            "origin_group": "new-origin",
            "rights_record_id": "synthetic-rights",
        }
    )
    new_config = BriefingConfig.from_mapping(raw)
    row = records[0].to_mapping()
    row.update(
        evidence_id="new-evidence",
        source_id="new-source",
        source_url="https://new.invalid/item",
        original_source_group="new-origin",
    )
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        ledger.ingest(config, records)
        ledger.ingest(new_config, (Evidence.from_mapping(row),))
        assert len(ledger.view(config, T).records) == 6
        assert len(ledger.view(new_config, T).records) == 7


def test_support_must_cover_every_domain_of_parent_claim(config, records):
    row = records[0].to_mapping()
    row.update(
        domain_ids=("elections", "government_policy"),
        evidence_status="corroborated",
        support_ids=("p2",),
    )
    with EvidenceLedger(":memory:", clock=lambda: T) as ledger:
        with pytest.raises(ValueError, match="cross-domain"):
            ledger.ingest(config, (Evidence.from_mapping(row), *records[1:]))
