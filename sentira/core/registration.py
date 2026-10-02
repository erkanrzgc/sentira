"""Small validation and canonicalisation helpers for offline registrations."""

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from urllib.parse import urlsplit

from sentira.core.document import utc, valid_slug

DOMAIN_IDS = frozenset({"elections", "government_policy", "regional_conflict"})


def exact(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys():
        raise ValueError("Missing required fields")
    if value.keys() - set(required) - set(optional):
        raise ValueError("Unknown fields")
    return value


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("A bounded integer is required")
    return value


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 10000:
        raise ValueError("A bounded non-empty string is required")
    if any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise ValueError("Control characters are not allowed")
    return value


def slug(value):
    if not valid_slug(value):
        raise ValueError("Invalid identifier")
    return value


def sequence(value, item=text):
    if not isinstance(value, (list, tuple)):
        raise ValueError("A sequence is required")
    result = tuple(item(v) for v in value)
    if len(set(result)) != len(result):
        raise ValueError("Duplicate entries")
    return result


def synthetic_url(value):
    text(value)
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme == "https"
            and parts.hostname
            and parts.hostname.endswith(".invalid")
            and not parts.username
            and not parts.password
            and not parts.port
            and not parts.query
            and not parts.fragment
            and not any(c.isspace() for c in value)
            and not any(c in value for c in '<>"\\')
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Only credential-free reserved synthetic URLs are allowed")
    return value


def normalise(value):
    if is_dataclass(value):
        return normalise(asdict(value))
    if isinstance(value, datetime):
        return utc(value).isoformat(timespec="microseconds")
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalise(v) for v in value]
    return value


def canonical(value):
    return json.dumps(normalise(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()
