"""The count command stamps the locked registration and protects its inputs."""

import re
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
    # Header and one row per grid cell, for the test span and the pre-origin span.
    assert text.count("\n| ") == 2 * (1 + len(locked.grid))
    assert "probability" not in text.lower() and "accuracy:" not in text.lower()
    assert "k_floor binds (of eligible)" in text
    assert re.search(r"\| \d+/\d+ \(\d+\.\d%\) \|", text)


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


@pytest.mark.parametrize(
    "segment",
    [
        "{ first = 2030-01-01T00:00:00Z, hours = 9600, per_hour = 1000 }",
        "{ first = 9999-12-31T00:00:00Z, hours = 100, per_hour = 1 }",
    ],
)
def test_count_cli_refuses_oversized_or_unrepresentable_series_before_expanding(
    tmp_path, monkeypatch, segment
):
    import sentira.series.synthetic as synthetic

    if "9600" in segment:
        # Refusal must come from arithmetic, before any row object is built.
        def forbidden(*args, **kwargs):
            raise AssertionError("rows were expanded before the size check")

        monkeypatch.setattr(synthetic, "Observation", forbidden)
    series = tmp_path / "series.toml"
    series.write_text(
        'mode = "synthetic"\nstart = 2030-01-01T00:00:00Z\nend = 2030-03-12T00:00:00Z\n\n'
        f'[[topics]]\nid = "large"\nsegments = [{segment}]\n',
        encoding="utf-8",
    )
    output = tmp_path / "count.md"
    assert main(arguments(output, series)) == 1
    assert not output.exists()


def test_series_segment_count_is_bounded():
    from datetime import UTC, datetime

    from sentira.series.synthetic import MAX_SEGMENTS, parse_series

    first = datetime(2030, 1, 1, tzinfo=UTC)
    raw = {
        "mode": "synthetic",
        "start": first,
        "end": datetime(2030, 2, 1, tzinfo=UTC),
        "topics": [
            {
                "id": "many",
                "segments": [{"first": first, "hours": 1, "per_hour": 0}] * (MAX_SEGMENTS + 1),
            }
        ],
    }
    with pytest.raises(ValueError, match="segments"):
        parse_series(raw)
