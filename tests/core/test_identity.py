import hashlib
import hmac
import json

import pytest

from sentira.core.identity import IdentifierKind, IdentityHasher


def test_hash_matches_independent_hmac_vector():
    key = bytes(range(32))
    message = json.dumps(["synthetic", "author", "sample"], separators=(",", ":")).encode()
    assert IdentityHasher(key).hash("synthetic", IdentifierKind.AUTHOR, "sample") == (
        hmac.new(key, message, hashlib.sha256).hexdigest()
    )


def test_platform_and_identifier_kind_are_separated():
    hasher = IdentityHasher(b"k" * 32)
    hashes = {
        hasher.hash(p, kind, "same")
        for p in ("synthetic-a", "synthetic-b")
        for kind in IdentifierKind
    }
    assert len(hashes) == 4


def test_parent_reference_resolves_to_comment_hash():
    hasher = IdentityHasher(b"k" * 32)
    assert hasher.hash("synthetic", IdentifierKind.PARENT, "parent-comment") == (
        hasher.hash("synthetic", IdentifierKind.COMMENT, "parent-comment")
    )


def test_missing_key_fails_at_startup(monkeypatch):
    monkeypatch.delenv("SENTIRA_HMAC_KEY", raising=False)
    with pytest.raises(ValueError):
        IdentityHasher.from_env()


@pytest.mark.parametrize("key", ["", "not-a-secret", "ab" * 31, "ab" * 33])
def test_invalid_env_key_is_not_echoed(monkeypatch, key):
    monkeypatch.setenv("SENTIRA_HMAC_KEY", key)
    with pytest.raises(ValueError) as exc:
        IdentityHasher.from_env()
    if key:
        assert key not in str(exc.value)


def test_valid_env_key_matches_explicit_key(monkeypatch):
    monkeypatch.setenv("SENTIRA_HMAC_KEY", "ab" * 32)
    assert IdentityHasher.from_env().hash("synthetic", IdentifierKind.COMMENT, "x") == (
        IdentityHasher(bytes.fromhex("ab" * 32)).hash("synthetic", IdentifierKind.COMMENT, "x")
    )


@pytest.mark.parametrize("key", [b"", b"short", "k" * 32, b"k" * 33])
def test_invalid_explicit_key_rejected(key):
    with pytest.raises(ValueError):
        IdentityHasher(key)


def test_secret_and_raw_identifier_not_in_diagnostics():
    hasher = IdentityHasher(b"private-key-marker".ljust(32, b"x"))
    assert "private-key-marker" not in repr(hasher)
    with pytest.raises(ValueError) as exc:
        hasher.hash("synthetic", "invalid-kind", "private-raw-marker")
    assert "private-raw-marker" not in str(exc.value)


@pytest.mark.parametrize(
    "platform,raw_id", [("", "x"), ("SYNTHETIC", "x"), ("synthetic", ""), ("synthetic", 3)]
)
def test_invalid_hash_input_rejected(platform, raw_id):
    with pytest.raises(ValueError):
        IdentityHasher(b"k" * 32).hash(platform, IdentifierKind.AUTHOR, raw_id)
