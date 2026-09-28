"""The synthetic fixture contract is validated before PDF authoring."""

import copy
import tomllib
from pathlib import Path

import pytest


def config():
    return tomllib.loads(Path("experiments/ocr/fixtures.toml").read_text(encoding="utf-8"))


def validate(value):
    from experiments.ocr.fixtures import validate_config

    return validate_config(value)


def test_original_fixture_config_validates():
    validate(config())


@pytest.mark.parametrize("value", [False, "true", 1, None])
def test_non_synthetic_declaration_rejected(value):
    settings = config()
    settings["synthetic"] = value
    with pytest.raises(ValueError):
        validate(settings)


@pytest.mark.parametrize("value", ["../escape", "duplicate", "CON", "UPPER"])
def test_unsafe_or_duplicate_family_id_rejected(value):
    settings = config()
    settings["families"][0]["id"] = value
    if value == "duplicate":
        settings["families"][1]["id"] = value
    with pytest.raises(ValueError):
        validate(settings)


def test_embedded_line_break_cannot_inject_extra_answer():
    settings = config()
    settings["families"][0]["fields"]["decision"] = "001\nDate: 2040-01-01"
    with pytest.raises(ValueError):
        validate(settings)


def test_missing_or_extra_field_rejected():
    settings = config()
    del settings["families"][0]["fields"]["scale"]
    with pytest.raises(ValueError):
        validate(settings)
    settings = config()
    settings["families"][0]["fields"]["person"] = "not allowed"
    with pytest.raises(ValueError):
        validate(settings)


def test_extra_family_and_boolean_numeric_setting_rejected():
    settings = config()
    settings["families"].append(copy.deepcopy(settings["families"][0]))
    with pytest.raises(ValueError):
        validate(settings)
    settings = config()
    settings["dpi"] = True
    with pytest.raises(ValueError):
        validate(settings)
