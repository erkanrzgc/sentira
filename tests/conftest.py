"""Original synthetic fixtures; no recorded platform content or network access."""

import socket
from datetime import UTC, datetime, timedelta

import pytest


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
