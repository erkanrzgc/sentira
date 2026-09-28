"""CLI output contracts; core evidence validation is exercised separately."""

import json

import pytest


def cli():
    from experiments.field_review import run

    return run


def test_packet_command_never_replaces_existing_output(tmp_path, monkeypatch):
    module = cli()
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "packet.json"
    marker.write_text("preserve this")
    monkeypatch.setattr(module, "build_packet", lambda *args: {})
    with pytest.raises(SystemExit) as exc:
        module.main(
            ["packet", "--fixtures", "unused", "--results", "unused", "--output", str(output)]
        )
    assert exc.value.code == 2
    assert marker.read_text() == "preserve this"


def test_packet_writes_no_automatic_decisions(tmp_path, monkeypatch):
    module = cli()
    packet = {"synthetic_development_only": True, "fields": []}
    monkeypatch.setattr(module, "build_packet", lambda *args: packet)
    output = tmp_path / "packet"
    module.main(["packet", "--fixtures", "unused", "--results", "unused", "--output", str(output)])
    import tomllib

    decisions = tomllib.loads((output / "decisions.toml").read_text())
    assert decisions == {"packet_sha256": module.packet_digest(packet), "reviews": []}
    assert json.loads((output / "packet.json").read_text()) == packet


def test_validation_failure_leaves_no_report_directory(tmp_path, monkeypatch):
    module = cli()

    def reject(*args):
        raise ValueError("Changed source page")

    monkeypatch.setattr(module, "build_packet", reject)
    output = tmp_path / "result"
    with pytest.raises(SystemExit) as exc:
        module.main(
            ["packet", "--fixtures", "unused", "--results", "unused", "--output", str(output)]
        )
    assert exc.value.code == 2
    assert not output.exists()


def test_report_requires_matching_decisions_before_creating_output(tmp_path, monkeypatch):
    module = cli()
    monkeypatch.setattr(module, "build_packet", lambda *args: {"fields": []})

    def reject(*args):
        raise ValueError("Review binding mismatch")

    monkeypatch.setattr(module, "apply_decisions", reject)
    decisions = tmp_path / "decisions.toml"
    decisions.write_text('packet_sha256 = "wrong"\nreviews = []\n')
    output = tmp_path / "result"
    with pytest.raises(SystemExit) as exc:
        module.main(
            [
                "report",
                "--fixtures",
                "unused",
                "--results",
                "unused",
                "--decisions",
                str(decisions),
                "--output",
                str(output),
            ]
        )
    assert exc.value.code == 2
    assert not output.exists()
