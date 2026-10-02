"""Original synthetic fixtures; no recorded platform content or network access."""

import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HAND_MEASURED = ROOT / "tests/fixtures/hand-measured.toml"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is disabled in tests")

    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        if hasattr(socket.socket, name):
            monkeypatch.setattr(socket.socket, name, blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fields():
    from sentira.core.document import DocumentKind, Provenance

    return dict(
        doc_hash="a" * 64,
        kind=DocumentKind.UTTERANCE,
        source="synthetic",
        published_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        text="Synthetic comment about public services.",
        author_hash="b" * 64,
        parent_hash=None,
        provenance=Provenance.SYNTHETIC,
    )


@pytest.fixture
def document(fields):
    from sentira.core.document import Document

    return Document(**fields)


@pytest.fixture(scope="session")
def hand_locked(tmp_path_factory):
    """The shipped registration with hand-chosen thresholds: c_min 6, k_floor 10, H 72 h."""
    from sentira.backtest.registration import load_locked, write_lock

    registration = ROOT / "examples/synthetic-registration.toml"
    lock = tmp_path_factory.mktemp("hand") / "registration.lock"
    write_lock(registration, HAND_MEASURED, lock)
    return load_locked(registration, HAND_MEASURED, lock)
