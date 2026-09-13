import pytest

from sentira.config.schema import Target, TargetKind, load_targets


@pytest.mark.parametrize("kind", ["party", "state_institution", "declared_candidate"])
def test_allowed_target_type_loaded(kind):
    assert load_targets([{"key": "target-a", "name": "Example institution", "kind": kind}]) == (
        Target(key="target-a", name="Example institution", kind=TargetKind(kind)),
    )


@pytest.mark.parametrize("kind", ["person", "journalist", "academic", "company", "PARTY"])
def test_target_of_disallowed_type_rejected_at_load(kind):
    with pytest.raises(ValueError):
        load_targets([{"key": "target-a", "name": "Example", "kind": kind}])


@pytest.mark.parametrize(
    "row",
    [
        {"key": "target-a", "name": "Example", "kind": "party", "profile_url": "private-marker"},
        {"key": "target-a", "name": "", "kind": "party"},
        {"key": "target-a", "name": 3, "kind": "party"},
        {"key": "", "name": "Example", "kind": "party"},
        {"name": "Example", "kind": "party"},
        "private-marker",
    ],
)
def test_malformed_target_rejected_without_echoing_input(row):
    with pytest.raises(ValueError) as exc:
        load_targets([row])
    assert "private-marker" not in str(exc.value)


def test_duplicate_target_keys_rejected():
    row = {"key": "target-a", "name": "Example", "kind": "party"}
    with pytest.raises(ValueError):
        load_targets([row, row])


def test_direct_target_constructor_enforces_types():
    with pytest.raises(ValueError):
        Target(key="target-a", name="Example", kind="person")


def test_empty_target_configuration_is_valid():
    assert load_targets([]) == ()
