"""The offline command protects both inputs and existing output."""

from pathlib import Path

import pytest

from sentira.cli import main


def arguments(output, source=Path("examples/synthetic-cases.toml")):
    return [
        "case-report",
        "--input",
        str(source),
        "--cutoff",
        "2030-02-03T00:00:00Z",
        "--issued-at",
        "2030-02-03T00:00:00Z",
        "--output",
        str(output),
    ]


def test_case_cli_renders(tmp_path):
    output = tmp_path / "report.md"
    assert main(arguments(output)) == 0
    assert "REVIEW REQUIRED" in output.read_text(encoding="utf-8")


def test_invalid_case_input_preserves_output(tmp_path):
    source = tmp_path / "invalid.toml"
    source.write_text("synthetic = false", encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("keep me", encoding="utf-8")
    assert main(arguments(output, source) + ["--overwrite"]) == 1
    assert output.read_text(encoding="utf-8") == "keep me"


def test_case_input_output_alias_rejected(tmp_path):
    source = tmp_path / "input.md"
    content = Path("examples/synthetic-cases.toml").read_bytes()
    source.write_bytes(content)
    assert main(arguments(source, source) + ["--overwrite"]) == 1
    assert source.read_bytes() == content


def test_case_overwrite_is_explicit(tmp_path):
    output = tmp_path / "report.md"
    output.write_text("keep me", encoding="utf-8")
    assert main(arguments(output)) == 1
    assert output.read_text(encoding="utf-8") == "keep me"
    assert main(arguments(output) + ["--overwrite"]) == 0
    assert "SYNTHETIC" in output.read_text(encoding="utf-8")


def test_case_cli_rejects_wrong_extension(tmp_path):
    output = tmp_path / "report.html"
    assert main(arguments(output)) == 1
    assert not output.exists()


def test_case_cli_rejects_bad_time(tmp_path):
    args = arguments(tmp_path / "report.md")
    args[args.index("--cutoff") + 1] = "2030-02-03"
    assert main(args) == 1


@pytest.mark.parametrize("value", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
def test_case_cli_rejects_unrepresentable_utc_without_overwriting(tmp_path, capsys, value):
    output = tmp_path / "report.md"
    output.write_text("keep me", encoding="utf-8")
    command = arguments(output)
    command[command.index("--cutoff") + 1] = value
    assert main([*command, "--overwrite"]) == 1
    assert output.read_text(encoding="utf-8") == "keep me"
    assert "Case report failed:" in capsys.readouterr().err
