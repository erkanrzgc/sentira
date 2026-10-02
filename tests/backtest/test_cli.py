"""The count command stamps the locked registration and protects its inputs."""

from pathlib import Path

import pytest

from sentira.cli import main

EXAMPLES = Path("examples")


def arguments(output, series=EXAMPLES / "synthetic-series.toml"):
    return [
        "count",
        "--registration",
        str(EXAMPLES / "synthetic-registration.toml"),
        "--measured",
        str(EXAMPLES / "synthetic-measured.toml"),
        "--lock",
        str(EXAMPLES / "synthetic-registration.lock"),
        "--series",
        str(series),
        "--output",
        str(output),
    ]


def test_count_cli_renders_stamped_report(tmp_path):
    from sentira.backtest.registration import load_locked

    locked = load_locked(
        EXAMPLES / "synthetic-registration.toml",
        EXAMPLES / "synthetic-measured.toml",
        EXAMPLES / "synthetic-registration.lock",
    )
    output = tmp_path / "count.md"
    assert main(arguments(output)) == 0
    text = output.read_text(encoding="utf-8")
    assert text.startswith("# SYNTHETIC surge count report")
    assert locked.registration_sha256 in text and locked.measured_sha256 in text
    assert "not backtestable on current history" in text
    assert text.count("\n| ") == 1 + len(locked.grid)
    assert "probability" not in text.lower() and "accuracy:" not in text.lower()


def test_count_cli_is_deterministic(tmp_path):
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    assert main(arguments(first)) == main(arguments(second)) == 0
    assert first.read_bytes() == second.read_bytes()


def test_count_cli_protects_existing_output_and_inputs(tmp_path, capsys):
    output = tmp_path / "count.md"
    output.write_text("operator notes", encoding="utf-8")
    assert main(arguments(output)) == 1
    assert output.read_text(encoding="utf-8") == "operator notes"
    assert main([*arguments(output), "--overwrite"]) == 0
    assert output.read_text(encoding="utf-8").startswith("# SYNTHETIC")
    for target in (tmp_path / "count.txt", EXAMPLES / "synthetic-series.toml"):
        assert main(arguments(target)) == 1
    assert "Count refused" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('mode = "synthetic"', 'mode = "live"'),
        ("per_hour = 1 }", "per_hour = -1 }"),
        ("start = 2030-01-01T00:00:00Z", "start = 2030-01-01T00:30:00Z"),
        ('id = "transport"', 'id = "Transport Topic"'),
    ],
)
def test_count_cli_rejects_invalid_series(tmp_path, old, new):
    series = tmp_path / "series.toml"
    text = (EXAMPLES / "synthetic-series.toml").read_text(encoding="utf-8")
    assert old in text
    series.write_text(text.replace(old, new, 1), encoding="utf-8")
    output = tmp_path / "count.md"
    assert main(arguments(output, series)) == 1
    assert not output.exists()
