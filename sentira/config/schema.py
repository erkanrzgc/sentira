"""Target type validation is structural, not verification of real-world status."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from sentira.core.document import valid_slug


class TargetKind(StrEnum):
    PARTY = "party"
    STATE_INSTITUTION = "state_institution"
    DECLARED_CANDIDATE = "declared_candidate"


@dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    key: str
    name: str
    kind: TargetKind

    def __post_init__(self) -> None:
        if not valid_slug(self.key):
            raise ValueError("Invalid target key")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("A target name is required")
        if not isinstance(self.kind, TargetKind):
            raise ValueError("Disallowed target type")


def load_targets(rows: Sequence[Mapping[str, object]]) -> tuple[Target, ...]:
    if not isinstance(rows, (list, tuple)):
        raise ValueError("Targets must be a list or tuple")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"key", "name", "kind"}:
            raise ValueError("Target fields do not match the contract")
        try:
            kind = TargetKind(row["kind"])
        except (ValueError, TypeError):
            raise ValueError("Disallowed target type") from None
        target = Target(key=row["key"], name=row["name"], kind=kind)
        if target.key in seen:
            raise ValueError("Duplicate target key")
        seen.add(target.key)
        result.append(target)
    return tuple(result)
