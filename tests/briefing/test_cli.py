from pathlib import Path
from shutil import copytree

import pytest

from sentira.cli import main

ROOT = Path(__file__).resolve().parents[2]


def args(output):
    return [
        "briefing",
        "--config",
        str(ROOT / "config"),
        "--evidence",
        str(ROOT / "examples/synthetic-evidence.toml"),
        "--observed-at",
        "2030-01-01T12:00:00Z",
        "--cutoff",
        "2030-01-01T12:00:00Z",
        "--issued-at",
        "2030-01-01T12:00:00Z",
        "--output",
        str(output),
    ]


def test_cli_produces_identical_reports_offline(tmp_path):
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    assert main(args(first)) == 0
    assert main(args(second)) == 0
    assert first.read_bytes() == second.read_bytes()
    assert b"SYNTHETIC" in first.read_bytes()


def test_cli_preserves_existing_output(tmp_path):
    path = tmp_path / "report.md"
    path.write_text("keep", encoding="utf-8")
    assert main(args(path)) == 1
    assert path.read_text("utf-8") == "keep"
    assert main([*args(path), "--overwrite"]) == 0


def test_cli_invalid_input_creates_no_report(tmp_path, capsys):
    path = tmp_path / "report.md"
    command = args(path)
    command[command.index("--observed-at") + 1] = "private-invalid-value"
    assert main(command) == 1
    assert not path.exists()
    assert "private-invalid-value" not in capsys.readouterr().err


def test_cli_never_overwrites_input(tmp_path):
    path = tmp_path / "input.md"
    path.write_text('mode = "synthetic"\nevidence = []', encoding="utf-8")
    command = args(path)
    command[command.index("--evidence") + 1] = str(path)
    assert main([*command, "--overwrite"]) == 1
    assert path.read_text("utf-8").startswith("mode")


@pytest.mark.parametrize("field", ["domain", "question_domain", "evidence_status"])
@pytest.mark.parametrize("value", ['["private-invalid-value"]', '{bad = "private-invalid-value"}'])
def test_cli_rejects_non_text_enums_without_exposing_input(tmp_path, capsys, field, value):
    directory = tmp_path / "config"
    copytree(ROOT / "config", directory)
    evidence = tmp_path / "evidence.toml"
    evidence.write_bytes((ROOT / "examples/synthetic-evidence.toml").read_bytes())
    if field == "domain":
        target, original = directory / "domains.toml", 'id = "elections"'
    elif field == "question_domain":
        target, original = directory / "questions.toml", 'domain_id = "elections"'
    else:
        target, original = evidence, 'evidence_status = "attributed"'
    content = target.read_text(encoding="utf-8")
    assert original in content
    key = original.split(" = ")[0]
    target.write_text(content.replace(original, f"{key} = {value}", 1), encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("keep existing report", encoding="utf-8")
    command = args(output)
    command[command.index("--config") + 1] = str(directory)
    command[command.index("--evidence") + 1] = str(evidence)
    assert main([*command, "--overwrite"]) == 1
    assert output.read_text(encoding="utf-8") == "keep existing report"
    captured = capsys.readouterr()
    assert "Briefing failed:" in captured.err
    assert "private-invalid-value" not in captured.err
    assert not captured.out


def test_cli_never_overwrites_symlinked_configuration(tmp_path):
    directory = tmp_path / "config"
    copytree(ROOT / "config", directory)
    output = tmp_path / "operator-config.md"
    original = (directory / "domains.toml").read_bytes()
    output.write_bytes(original)
    link = directory / "domains.toml"
    link.unlink()
    try:
        link.symlink_to(output)
    except OSError as error:
        pytest.skip(f"Symbolic links unavailable: {error}")
    command = args(output)
    command[command.index("--config") + 1] = str(directory)
    assert main([*command, "--overwrite"]) == 1
    assert output.read_bytes() == original
    assert link.read_bytes() == original
