from pathlib import Path

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
