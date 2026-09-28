import hashlib
import json

import pytest

from experiments.ocr.scoring import (
    baseline_predictions,
    extract_fields,
    score_fields,
    verify_lock,
)


def test_extraction_preserves_digits_units_case_and_internal_whitespace():
    text = " Ref: 001/A  b \nDuration: 1 calendar month\nScale: 1:5000"
    result = extract_fields(text, {"reference": "Ref", "duration": "Duration", "scale": "Scale"})
    assert result == {
        "reference": {"status": "found", "value": "001/A  b"},
        "duration": {"status": "found", "value": "1 calendar month"},
        "scale": {"status": "found", "value": "1:5000"},
    }


@pytest.mark.parametrize("text", ["", "prefix Ref: 001", "ref: 001", "Ref : 001", "Ref:   "])
def test_missing_field_requires_exact_nonempty_labelled_line(text):
    assert extract_fields(text, {"reference": "Ref"}) == {
        "reference": {"status": "missing", "value": None}
    }


@pytest.mark.parametrize("text", ["Ref: 001\nRef: 001", "Ref: 001\nRef: 002", "Ref:\nRef:"])
def test_repeated_matching_lines_are_ambiguous(text):
    assert extract_fields(text, {"reference": "Ref"})["reference"] == {
        "status": "ambiguous",
        "value": None,
    }


@pytest.mark.parametrize("actual", ["01", "001 ", "001/A", "001  B", "1 month", "30 days"])
def test_scoring_never_normalises_changed_values(actual):
    expected = {"reference": "001", "duration": "1 calendar month"}
    extracted = {"reference": {"status": "found", "value": actual}}
    result = score_fields(expected, extracted)
    assert result["reference"] == {
        "expected": "001",
        "actual": actual,
        "status": "found",
        "match": False,
    }
    assert result["duration"] == {
        "expected": "1 calendar month",
        "actual": None,
        "status": "missing",
        "match": False,
    }


def test_scoring_counts_only_found_exact_values():
    result = score_fields(
        {"a": "001", "b": "001"},
        {"a": {"status": "found", "value": "001"}, "b": {"status": "ambiguous", "value": "001"}},
    )
    assert result["a"]["match"] is True
    assert result["b"]["match"] is False


def test_baselines_use_family_inventory_and_are_order_invariant():
    families = [
        {"id": name, "fields": {"reference": value}}
        for name, value in [("alpha", "B"), ("beta", "A"), ("gamma", "B"), ("delta", "A")]
    ]
    first = baseline_predictions(families, ["reference"], 27092026)
    assert first == baseline_predictions(list(reversed(families)), ["reference"], 27092026)
    assert all(row["majority"] == {"reference": "A"} for row in first.values())
    for family in families:
        index = (
            int(hashlib.sha256(f"27092026:{family['id']}:reference".encode()).hexdigest(), 16) % 2
        )
        assert first[family["id"]]["random"]["reference"] == ["A", "B"][index]


def make_lock(directory, files=None):
    (directory / "input.txt").write_bytes(b"original")
    registration = {
        "files": files
        if files is not None
        else {"input.txt": hashlib.sha256(b"original").hexdigest()},
        "metadata": "retained",
    }
    raw = json.dumps(registration).encode()
    (directory / "registration.json").write_bytes(raw)
    (directory / "registration.sha256").write_text(hashlib.sha256(raw).hexdigest())
    return registration


def test_lock_returns_registration_without_mutating_files(tmp_path):
    expected = make_lock(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert verify_lock(tmp_path) == expected
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("name", ["registration.json", "registration.sha256", "input.txt"])
def test_lock_rejects_modified_registered_bytes_without_repair(tmp_path, name):
    make_lock(tmp_path)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b" ")
    # A lock file permits trailing newline, so damage the digest itself.
    if name == "registration.sha256":
        path.write_bytes(b"0" * 64)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        verify_lock(tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize(
    "name",
    [
        "../outside.txt",
        "nested/../../outside.txt",
        "/absolute.txt",
        "C:\\outside.txt",
        "..\\outside.txt",
    ],
)
def test_lock_rejects_paths_outside_registered_directory(tmp_path, name):
    make_lock(tmp_path, {name: "0" * 64})
    with pytest.raises(ValueError):
        verify_lock(tmp_path)


def test_lock_rejects_outside_symlink(tmp_path):
    directory = tmp_path / "locked"
    directory.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"original")
    make_lock(directory)
    link = directory / "input.txt"
    link.unlink()
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires host permission")
    with pytest.raises(ValueError):
        verify_lock(directory)


@pytest.mark.parametrize("raw", [b"[]", b'{"files": []}', b"{}", b"not json"])
def test_lock_rejects_invalid_registration_structure(tmp_path, raw):
    (tmp_path / "registration.json").write_bytes(raw)
    (tmp_path / "registration.sha256").write_text(hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        verify_lock(tmp_path)


def test_lock_rejects_missing_lock(tmp_path):
    with pytest.raises(ValueError):
        verify_lock(tmp_path)
