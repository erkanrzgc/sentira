"""Fresh output directories and byte-level input provenance."""

import hashlib
import json

import pytest

from experiments.eligibility import run


@pytest.fixture
def invocation(tmp_path, monkeypatch):
    decision = tmp_path / "decisions.toml"
    context = tmp_path / "context.toml"
    decision.write_bytes(b"# Exact bytes\r\nreviews = []\r\n")
    context.write_bytes(b"synthetic = true\n")
    output = tmp_path / "output"
    monkeypatch.setattr(
        run,
        "build_packet",
        lambda *args: {"registration_sha256": "a" * 64, "results_sha256": "b" * 64},
    )
    monkeypatch.setattr(run, "evaluate", lambda *args: {"fields": []})
    monkeypatch.setattr(run, "render_report", lambda result: "Synthetic candidates\n")
    argv = [
        "--fixtures",
        "unused",
        "--results",
        "unused",
        "--decisions",
        str(decision),
        "--context",
        str(context),
        "--cutoff",
        "2026-01-02T00:00:00+00:00",
        "--output",
        str(output),
    ]
    return argv, output, decision, context


def test_exact_input_hashes_and_report_written(invocation):
    argv, output, decision, context = invocation
    run.main(argv)
    result = json.loads((output / "eligibility.json").read_text())
    assert result["input_sha256"] == {
        "registration": "a" * 64,
        "results": "b" * 64,
        "decisions": hashlib.sha256(decision.read_bytes()).hexdigest(),
        "context": hashlib.sha256(context.read_bytes()).hexdigest(),
    }
    assert (output / "report.md").read_text() == "Synthetic candidates\n"


def test_existing_output_is_preserved(invocation):
    argv, output, _, _ = invocation
    output.mkdir()
    marker = output / "eligibility.json"
    marker.write_text("preserve")
    with pytest.raises(SystemExit) as exc:
        run.main(argv)
    assert exc.value.code == 2
    assert marker.read_text() == "preserve"


@pytest.mark.parametrize("stage", ["build_packet", "evaluate", "render_report"])
def test_invalid_inputs_leave_no_directory(invocation, monkeypatch, stage):
    argv, output, _, _ = invocation

    def reject(*args):
        raise ValueError("Invalid synthetic evidence")

    monkeypatch.setattr(run, stage, reject)
    with pytest.raises(SystemExit) as exc:
        run.main(argv)
    assert exc.value.code == 2
    assert not output.exists()


def test_invalid_utf8_leaves_no_directory(invocation):
    argv, output, _, context = invocation
    context.write_bytes(b"\xff")
    with pytest.raises(SystemExit) as exc:
        run.main(argv)
    assert exc.value.code == 2
    assert not output.exists()
