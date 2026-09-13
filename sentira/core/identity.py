"""Domain-separated boundary hashing; keys and raw identifiers are never logged."""

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from enum import StrEnum

from sentira.core.document import valid_slug


class IdentifierKind(StrEnum):
    AUTHOR = "author"
    COMMENT = "comment"
    # A parent reference identifies a comment, not a third entity type.
    PARENT = "comment"


@dataclass(frozen=True, slots=True)
class IdentityHasher:
    key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.key, bytes) or len(self.key) != 32:
            raise ValueError("HMAC key must contain exactly 32 bytes")

    @classmethod
    def from_env(cls) -> "IdentityHasher":
        encoded = os.environ.get("SENTIRA_HMAC_KEY", "")
        if len(encoded) != 64:
            raise ValueError("SENTIRA_HMAC_KEY must contain 64 hexadecimal characters")
        try:
            key = bytes.fromhex(encoded)
        except ValueError:
            raise ValueError("SENTIRA_HMAC_KEY must contain 64 hexadecimal characters") from None
        return cls(key)

    def hash(self, platform: str, kind: IdentifierKind, raw_id: str) -> str:
        if not valid_slug(platform) or not isinstance(kind, IdentifierKind):
            raise ValueError("Invalid identity namespace")
        if not isinstance(raw_id, str) or not raw_id:
            raise ValueError("Identity input must be a non-empty string")
        message = json.dumps([platform, kind.value, raw_id], separators=(",", ":")).encode("utf-8")
        return hmac.new(self.key, message, hashlib.sha256).hexdigest()
