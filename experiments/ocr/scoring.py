"""Exact field scoring and input integrity for the offline OCR experiment."""

import hashlib
import json
from collections import Counter
from pathlib import Path, PureWindowsPath


def extract_fields(text: str, labels: dict[str, str]) -> dict:
    """Extract labelled lines without consulting expected values."""
    lines = [line.strip() for line in text.splitlines()]
    result = {}
    for field, label in labels.items():
        prefix = label + ":"
        values = [line[len(prefix) :].strip() for line in lines if line.startswith(prefix)]
        if len(values) > 1:
            result[field] = {"status": "ambiguous", "value": None}
        elif not values or not values[0]:
            result[field] = {"status": "missing", "value": None}
        else:
            result[field] = {"status": "found", "value": values[0]}
    return result


def score_fields(expected: dict[str, str], extracted: dict) -> dict:
    """Keep every expected field in the denominator, including failed extraction."""
    result = {}
    for field, value in expected.items():
        observed = extracted.get(field, {"status": "missing", "value": None})
        result[field] = {
            "expected": value,
            "actual": observed["value"],
            "status": observed["status"],
            "match": observed["status"] == "found" and observed["value"] == value,
        }
    return result


def baseline_predictions(families: list[dict], field_names: list[str], seed: int) -> dict:
    """Predict once per family, using its shared development label inventory."""
    result = {family["id"]: {"majority": {}, "random": {}} for family in families}
    for field in field_names:
        counts = Counter(family["fields"][field] for family in families)
        inventory = sorted(counts)
        if not inventory:
            continue
        majority = min(inventory, key=lambda value: (-counts[value], value))
        for family in families:
            family_id = family["id"]
            digest = hashlib.sha256(f"{seed}:{family_id}:{field}".encode()).digest()
            result[family_id]["majority"][field] = majority
            result[family_id]["random"][field] = inventory[
                int.from_bytes(digest, "big") % len(inventory)
            ]
    return result


def _registered_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name:
        raise ValueError("Registered filename must be a nonempty relative path")
    relative = Path(name)
    windows = PureWindowsPath(name)
    if relative.is_absolute() or windows.drive or windows.root or ".." in windows.parts:
        raise ValueError(f"Invalid registered path: {name}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Registered path escapes its directory: {name}")
    return target


def verify_lock(directory: Path) -> dict:
    """Verify raw registration and registered file bytes; never repair a lock."""
    try:
        root = Path(directory).resolve()
        raw = _registered_path(root, "registration.json").read_bytes()
        lock = _registered_path(root, "registration.sha256").read_text(encoding="ascii").strip()
        if hashlib.sha256(raw).hexdigest() != lock:
            raise ValueError("Registration digest mismatch")
        registration = json.loads(raw)
        if not isinstance(registration, dict) or not isinstance(registration.get("files"), dict):
            raise ValueError("Registration must contain a files mapping")
        for name, expected in registration["files"].items():
            target = _registered_path(root, name)
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Registered file digest mismatch: {name}")
        return registration
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
        raise ValueError(f"Invalid registration lock: {exc}") from exc
