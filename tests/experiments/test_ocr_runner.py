"""Synthetic engine failures, with no native engine or network calls."""

import importlib.metadata
import platform
import subprocess

import pytest


def runner():
    from experiments.ocr import run

    return run


def test_missing_recognition_data_does_not_invoke_engine(tmp_path, monkeypatch):
    module = runner()

    def forbidden(*args, **kwargs):
        pytest.fail("Engine called without recognition data")

    monkeypatch.setattr(subprocess, "run", forbidden)
    result = module.recognise(tmp_path / "page.png", "engine", tmp_path, "fixture", 30, 6, 1)
    assert result["status"] == "not_run_missing_recognition_data"
    assert result["elapsed_seconds"] is None


def test_timeout_keeps_partial_output_without_scoring_it(tmp_path, monkeypatch):
    module = runner()
    (tmp_path / "fixture.traineddata").write_bytes(b"synthetic data")

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 30
        assert kwargs.get("shell", False) is False
        raise subprocess.TimeoutExpired(args[0], 30, output=b"Decision: 001", stderr=b"partial")

    monkeypatch.setattr(subprocess, "run", timeout)
    result = module.recognise(tmp_path / "page.png", "engine", tmp_path, "fixture", 30, 6, 1)
    assert result["status"] == "timeout"
    assert result["raw_text"] == "Decision: 001"
    assert result["stderr"] == "partial"
    assert result["elapsed_seconds"] >= 0


def test_engine_failure_is_not_successful_text(tmp_path, monkeypatch):
    module = runner()
    (tmp_path / "fixture.traineddata").write_bytes(b"synthetic data")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, "partial", "bad")
    )
    result = module.recognise(tmp_path / "page.png", "engine", tmp_path, "fixture", 30, 6, 1)
    assert result["status"] == "engine_error"
    assert result["raw_text"] == "partial"


def test_external_dependency_change_rejected_before_run(tmp_path):
    module = runner()
    engine = tmp_path / "fake-engine"
    engine.write_bytes(b"original")
    registration = {"external_files": {str(engine): module.digest(engine)}}
    module.verify_external(registration)
    engine.write_bytes(b"modified")
    with pytest.raises(ValueError, match="dependency"):
        module.verify_external(registration)


def test_changed_library_version_rejected(monkeypatch):
    module = runner()
    registration = {"python_version": platform.python_version(), "libraries": {"pypdf": "1.0"}}
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "2.0")
    with pytest.raises(ValueError, match="version"):
        module.verify_versions(registration)


def test_changed_python_version_rejected():
    module = runner()
    with pytest.raises(ValueError, match="version"):
        module.verify_versions({"python_version": "0.0", "libraries": {}})


def test_invalid_utf8_is_preserved_and_never_called_success(tmp_path, monkeypatch):
    import base64

    module = runner()
    (tmp_path / "fixture.traineddata").write_bytes(b"synthetic data")
    raw = b"Decision: 001\nUnreadable: \xff"
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, raw, b"")
    )
    result = module.recognise(tmp_path / "page.png", "engine", tmp_path, "fixture", 30, 6, 1)
    assert result["status"] == "unreadable_output"
    assert result["raw_text"] == ""
    assert base64.b64decode(result["raw_stdout_base64"]) == raw


def test_running_code_must_match_registration_even_from_another_checkout():
    module = runner()
    with pytest.raises(ValueError, match="code"):
        module.verify_code({"code_files": {"run.py": "0" * 64}})
