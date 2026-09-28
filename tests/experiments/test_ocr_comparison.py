"""Exercise the locked comparison without PDF dependencies or native processes."""

import json
import platform
import tomllib
from pathlib import Path

import pytest

from experiments.ocr import run


def registered(tmp_path):
    directory = tmp_path / "fixture"
    directory.mkdir()
    config = tomllib.loads(Path("experiments/ocr/fixtures.toml").read_text(encoding="utf-8"))
    pages = []
    for family in config["families"]:
        for representation in ("text", "image"):
            name = f"{family['id']}-{representation}"
            for extension in ("pdf", "png"):
                (directory / f"{name}.{extension}").write_bytes(b"synthetic placeholder")
            pages.append(
                {
                    "id": name,
                    "family": family["id"],
                    "representation": representation,
                    "pdf": f"{name}.pdf",
                    "png": f"{name}.png",
                }
            )
    run.write_json(
        directory / "registration.json",
        {
            "files": {p.name: run.digest(p) for p in directory.iterdir()},
            "external_files": {},
            "code_files": {p.name: run.digest(p) for p in Path(run.__file__).parent.glob("*.py")},
            "python_version": platform.python_version(),
            "libraries": {},
            "pages": pages,
            "config": config,
            "engine": "unused",
            "data": "unused",
            "language": "fixture",
        },
    )
    return directory


def test_comparison_refuses_missing_visual_review_before_any_output(tmp_path):
    directory = registered(tmp_path)
    (directory / "registration.sha256").write_text(run.digest(directory / "registration.json"))
    with pytest.raises(ValueError, match="review"):
        run.compare(directory, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_changed_fixture_stops_before_any_engine_call(tmp_path, monkeypatch):
    directory = registered(tmp_path)
    run.lock(directory, True)
    (directory / "fixture-a-image.png").write_bytes(b"modified")
    monkeypatch.setattr(run, "recognise", lambda *a: pytest.fail("Engine must not run"))
    with pytest.raises(ValueError, match="digest"):
        run.compare(directory, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_failed_pages_remain_in_report_denominator(tmp_path, monkeypatch):
    directory = registered(tmp_path)
    run.lock(directory, True)
    monkeypatch.setattr(
        run,
        "pdf_text",
        lambda *a: {
            "status": "ok",
            "raw_text": "",
            "elapsed_seconds": 0.1,
        },
    )
    monkeypatch.setattr(
        run,
        "recognise",
        lambda *a: {
            "status": "timeout",
            "raw_text": "Scale: 1/1000",
            "elapsed_seconds": 30,
        },
    )
    report = run.compare(directory, tmp_path / "result")
    assert len(report["results"]) == 16
    assert all(not f["match"] for row in report["results"] for f in row["fields"].values())
    rendered = (tmp_path / "result/results.md").read_text(encoding="utf-8")
    assert "| ocr | image | 0/16 | 6/16 |" in rendered
    assert (
        json.loads((tmp_path / "result/results.json").read_text())["results"] == report["results"]
    )
    before = (tmp_path / "result/results.json").read_bytes()
    with pytest.raises(FileExistsError):
        run.compare(directory, tmp_path / "result")
    assert (tmp_path / "result/results.json").read_bytes() == before


def test_lock_requires_explicit_review_and_never_replaces_existing_lock(tmp_path):
    directory = registered(tmp_path)
    with pytest.raises(ValueError, match="inspection"):
        run.lock(directory, False)
    assert not (directory / "registration.sha256").exists()
    run.lock(directory, True)
    before = (directory / "registration.sha256").read_bytes()
    with pytest.raises(FileExistsError):
        run.lock(directory, True)
    assert (directory / "registration.sha256").read_bytes() == before
