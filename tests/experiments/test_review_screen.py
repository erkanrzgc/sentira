"""Standalone synthetic screen and cross-language decision contracts."""

import base64
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from experiments.field_review.core import apply_decisions, build_packet, packet_digest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@pytest.fixture
def inputs(tmp_path):
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9WQAAAAASUVORK5CYII="
    )
    (tmp_path / "page.png").write_bytes(image)
    reg = {
        "config": {"synthetic": True, "labels": {"date": "Date", "scale": "Scale"}},
        "pages": [{"id": "page", "png": "page.png"}],
        "files": {"page.png": hashlib.sha256(image).hexdigest()},
    }
    raw = json.dumps(reg).encode()
    (tmp_path / "registration.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / "registration.sha256").write_text(digest)
    result = {
        "registration_sha256": digest,
        "synthetic_development_only": True,
        "results": [
            {
                "method": "ocr",
                "page": "page",
                "status": "ok",
                "fields": {
                    "date": {
                        "actual": "</script><script>alert(1)</script>",
                        "status": "found",
                        "expected": "SECRET",
                    },
                    "scale": {"actual": None, "status": "missing", "expected": "SECRET"},
                },
            }
        ],
    }
    path = tmp_path / "results.json"
    path.write_text(json.dumps(result))
    return tmp_path, path


def test_standalone_packet_binding_images_and_injection(inputs, tmp_path):
    from experiments.review_screen.run import generate

    target = generate(*inputs, tmp_path / "screen")
    text = target.read_text(encoding="utf-8")
    data = json.loads(
        re.search(r'<script id="review-data" type="application/json">(.*?)</script>', text, re.S)[1]
    )
    packet = build_packet(*inputs)
    assert data["packet"] == packet
    assert data["packet_sha256"] == packet_digest(packet)
    assert "SECRET" not in text
    assert "</script><script>alert(1)</script>" not in text
    assert data["images"]["page.png"].startswith("data:image/png;base64,")
    assert "default-src 'none'" in text
    assert "fetch(" not in text


def test_fresh_directory_and_tampering_leave_no_output(inputs, tmp_path):
    from experiments.review_screen.run import generate

    output = tmp_path / "screen"
    output.mkdir()
    with pytest.raises(FileExistsError):
        generate(*inputs, output)
    (inputs[0] / "page.png").write_bytes(b"changed")
    absent = tmp_path / "absent"
    with pytest.raises(ValueError, match="digest mismatch"):
        generate(*inputs, absent)
    assert not absent.exists()


@pytest.mark.skipif(NODE is None, reason="Node.js is required for cross-language export checks")
@pytest.mark.parametrize("action", ["pending", "accept", "correct", "withhold"])
def test_javascript_toml_round_trip(inputs, action):
    packet = build_packet(*inputs)
    packet["fields"][0]["id"] += '"\\back\n\x7f'
    payload = {"packet": packet, "packet_sha256": packet_digest(packet)}
    review = {
        "action": action,
        "value": 'quote " slash \\bar \\foo emoji \U0001f680',
        "reason": 'Reason " \\ \U0001f680',
    }
    script = (
        "const fs=require('node:fs');"
        "const m=require('./experiments/review_screen/model.js');"
        "const x=JSON.parse(fs.readFileSync(0,'utf8'));"
        "process.stdout.write(m.exportToml(x.payload,"
        "new Map([[x.payload.packet.fields[0].id,x.review]])));"
    )
    result = subprocess.run(
        [NODE, "-e", script],
        input=json.dumps({"payload": payload, "review": review}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=ROOT,
        check=True,
    )
    decoded = tomllib.loads(result.stdout)
    rows = apply_decisions(packet, decoded)
    assert rows[1]["status"] == "pending"
    assert (
        rows[0]["status"]
        == {
            "pending": "pending",
            "accept": "accepted",
            "correct": "corrected",
            "withhold": "withheld",
        }[action]
    )
    if action == "correct":
        assert rows[0]["value"] == review["value"]
        assert rows[0]["reason"] == review["reason"]


def test_image_bytes_are_rechecked_after_packet_build(inputs, tmp_path, monkeypatch):
    from experiments.review_screen import run

    original = run.build_packet

    def changed_image(*args):
        packet = original(*args)
        (inputs[0] / "page.png").write_bytes(b"changed between reads")
        return packet

    monkeypatch.setattr(run, "build_packet", changed_image)
    output = tmp_path / "screen"
    with pytest.raises(ValueError, match="Image digest mismatch"):
        run.generate(*inputs, output)
    assert not output.exists()


def test_registered_non_png_is_refused_before_output(inputs, tmp_path):
    from experiments.review_screen.run import generate

    (inputs[0] / "page.png").write_bytes(b"<svg/>")
    reg_path = inputs[0] / "registration.json"
    reg = json.loads(reg_path.read_text())
    reg["files"]["page.png"] = hashlib.sha256(b"<svg/>").hexdigest()
    raw = json.dumps(reg).encode()
    reg_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (inputs[0] / "registration.sha256").write_text(digest)
    results = json.loads(inputs[1].read_text())
    results["registration_sha256"] = digest
    inputs[1].write_text(json.dumps(results))
    output = tmp_path / "screen"
    with pytest.raises(ValueError, match="PNG"):
        generate(*inputs, output)
    assert not output.exists()
