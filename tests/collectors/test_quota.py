"""The quota ledger is debited before every call; synthetic transports only."""

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "examples/synthetic-quota.toml"
T0 = datetime(2030, 1, 1, 12, tzinfo=UTC)
ENDPOINTS = ("playlistItems.list", "commentThreads.list", "videos.list")


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def policy_text(**reservations):
    values = {"live": 6000, "retrieval": 3000, "survival": 500, "buffer": 500, **reservations}
    text = POLICY.read_text(encoding="utf-8")
    for name, value in values.items():
        default = {"live": 6000, "retrieval": 3000, "survival": 500, "buffer": 500}[name]
        text = text.replace(f"{name} = {default}\n", f"{name} = {value}\n", 1)
    total = sum(values.values())
    return text.replace("daily_units = 10000", f"daily_units = {total}", 1)


def small_policy(tmp_path, **reservations):
    from sentira.config.quota import load_quota_policy

    path = tmp_path / "quota.toml"
    path.write_text(policy_text(**reservations), encoding="utf-8")
    return load_quota_policy(path)


class Transport:
    """Records calls and checks that each one was debited before it ran."""

    def __init__(self, ledger, fail_on=()):
        self.ledger = ledger
        self.calls = []
        self.fail_on = set(fail_on)

    def __call__(self, endpoint, params):
        debits = self.ledger.debits()
        assert debits and debits[-1].endpoint == endpoint and debits[-1].outcome == "pending"
        self.calls.append((endpoint, params))
        if len(self.calls) in self.fail_on:
            raise RuntimeError("synthetic transport failure")
        return {"endpoint": endpoint, "params": params}


def test_shipped_policy_matches_the_calculated_reservations():
    from sentira.config.quota import load_quota_policy

    policy = load_quota_policy(POLICY)
    assert policy.daily_units == 10000
    assert dict(policy.reservations) == {
        "live": 6000,
        "retrieval": 3000,
        "survival": 500,
        "buffer": 500,
    }
    assert policy.buffer_purposes == ("live",)
    assert policy.cost("commentThreads.list") == 1
    with pytest.raises(ValueError):
        policy.cost("search.list")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("daily_units = 10000", "daily_units = 9999"),
        ("buffer = 500\n", "buffer = 500\nspare = 0\n"),
        ("survival = 500\nbuffer = 500\n", "survival = -500\nbuffer = 1500\n"),
        ('purposes = ["live"]', 'purposes = ["buffer"]'),
        ('"videos.list" = 1', '"videos.list" = 1\n"search.list" = 1'),
        ('"videos.list" = 1', '"videos list" = 1'),
        ('"videos.list" = 1', '"videos.list" = 0'),
        ('"videos.list" = 1', '"commentThreads.insert" = 1'),
        ('"playlistItems.list" = 1\n"commentThreads.list" = 1\n"videos.list" = 1\n', ""),
        ('mode = "synthetic"', 'mode = "live"'),
        ("quota_day_utc_offset_minutes = 0", "quota_day_utc_offset_minutes = 7"),
    ],
)
def test_policy_reservations_must_sum_to_daily_units(tmp_path, old, new):
    from sentira.config.quota import load_quota_policy

    text = POLICY.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "quota.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        load_quota_policy(path)


def test_ledger_debited_before_call(tmp_path):
    from sentira.collectors.quota import MeteredClient
    from sentira.storage.quota import QuotaLedger

    with QuotaLedger(":memory:", small_policy(tmp_path), clock=Clock()) as ledger:
        transport = Transport(ledger)
        client = MeteredClient(transport, ledger)
        client.call("retrieval", "commentThreads.list", {"page": 1})
        client.call("live", "playlistItems.list", {"page": 1})
        assert [d.outcome for d in ledger.debits()] == ["ok", "ok"]
        assert len(transport.calls) == 2


def test_ledger_units_equal_calls_made(tmp_path):
    from sentira.collectors.quota import MeteredClient
    from sentira.storage.quota import QuotaExhausted, QuotaLedger

    policy = small_policy(tmp_path, live=40, retrieval=30, survival=5, buffer=10)
    generator = random.Random(5)
    clock = Clock()
    with QuotaLedger(":memory:", policy, clock=clock) as ledger:
        transport = Transport(ledger, fail_on={3, 17, 44})
        client = MeteredClient(transport, ledger)
        refused = 0
        for step in range(200):
            clock.now = T0 + timedelta(minutes=step)
            purpose = generator.choice(("live", "retrieval", "survival"))
            endpoint = generator.choice(ENDPOINTS)
            try:
                client.call(purpose, endpoint, {"step": step})
            except QuotaExhausted:
                refused += 1
            except RuntimeError:
                pass
        debits = ledger.debits()
        assert len(debits) == len(transport.calls) == 85
        assert sum(d.units for d in debits) == sum(policy.cost(e) for e, _ in transport.calls)
        assert refused == 200 - 85
        assert sum(d.outcome == "failed" for d in debits) == 3


def test_exhaustion_stops_cleanly_and_persists_collected(tmp_path):
    from sentira.collectors.quota import MeteredClient, drain
    from sentira.storage.quota import QuotaLedger

    path = tmp_path / "ledger.sqlite3"
    policy = small_policy(tmp_path, retrieval=5)
    collected = []
    with QuotaLedger(path, policy, clock=Clock()) as ledger:
        transport = Transport(ledger)
        requests = [("retrieval", "commentThreads.list", {"page": n}) for n in range(10)]
        result = drain(requests, MeteredClient(transport, ledger), collected.append)
    assert (result.completed, result.stopped) == (5, "quota_exhausted")
    assert [item["params"]["page"] for item in collected] == [0, 1, 2, 3, 4]
    assert len(transport.calls) == 5
    with QuotaLedger(path, policy, clock=Clock(T0 + timedelta(hours=1))) as reopened:
        assert len(reopened.debits()) == 5


def test_drain_reports_completion_when_quota_suffices(tmp_path):
    from sentira.collectors.quota import MeteredClient, drain
    from sentira.storage.quota import QuotaLedger

    collected = []
    with QuotaLedger(":memory:", small_policy(tmp_path), clock=Clock()) as ledger:
        client = MeteredClient(Transport(ledger), ledger)
        requests = [("survival", "videos.list", {"page": n}) for n in range(3)]
        result = drain(requests, client, collected.append)
        assert (result.completed, result.stopped) == (3, None)
        with pytest.raises(ValueError):
            MeteredClient(None, ledger)
        with pytest.raises(ValueError):
            drain(requests, object(), collected.append)
    assert len(collected) == 3


def test_retrieval_cannot_spend_live_reservation(tmp_path):
    from sentira.storage.quota import QuotaExhausted, QuotaLedger

    policy = small_policy(tmp_path, live=3, retrieval=2, survival=1, buffer=2)
    with QuotaLedger(":memory:", policy, clock=Clock()) as ledger:
        for _ in range(2):
            ledger.debit("retrieval", "commentThreads.list")
        with pytest.raises(QuotaExhausted):
            ledger.debit("retrieval", "commentThreads.list")
        ledger.debit("survival", "commentThreads.list")
        with pytest.raises(QuotaExhausted):
            ledger.debit("survival", "commentThreads.list")
        # Live keeps its whole reservation and alone may overflow into the buffer.
        for _ in range(5):
            ledger.debit("live", "playlistItems.list")
        with pytest.raises(QuotaExhausted):
            ledger.debit("live", "playlistItems.list")
        assert ledger.spent() == {"live": 3, "retrieval": 2, "survival": 1, "buffer": 2}


def test_unregistered_endpoint_refused_before_any_debit(tmp_path):
    from sentira.collectors.quota import MeteredClient
    from sentira.storage.quota import QuotaLedger

    with QuotaLedger(":memory:", small_policy(tmp_path), clock=Clock()) as ledger:
        transport = Transport(ledger)
        client = MeteredClient(transport, ledger)
        for endpoint in ("search.list", "channels.list", "commentThreads.insert"):
            with pytest.raises(ValueError):
                client.call("live", endpoint, {})
        with pytest.raises(ValueError):
            client.call("marketing", "videos.list", {})
        assert ledger.debits() == () and transport.calls == []


def test_quota_day_resets_at_registered_offset(tmp_path):
    from sentira.config.quota import load_quota_policy
    from sentira.storage.quota import QuotaExhausted, QuotaLedger

    path = tmp_path / "quota.toml"
    text = policy_text(retrieval=2).replace(
        "quota_day_utc_offset_minutes = 0", "quota_day_utc_offset_minutes = -480"
    )
    path.write_text(text, encoding="utf-8")
    policy = load_quota_policy(path)
    # With a registered offset of -8 h, the quota day turns over at 08:00 UTC.
    clock = Clock(datetime(2030, 1, 1, 7, tzinfo=UTC))
    with QuotaLedger(":memory:", policy, clock=clock) as ledger:
        ledger.debit("retrieval", "commentThreads.list")
        ledger.debit("retrieval", "commentThreads.list")
        clock.now = datetime(2030, 1, 1, 7, 59, 59, tzinfo=UTC)
        with pytest.raises(QuotaExhausted):
            ledger.debit("retrieval", "commentThreads.list")
        clock.now = datetime(2030, 1, 1, 8, tzinfo=UTC)
        ledger.debit("retrieval", "commentThreads.list")
        days = [debit.quota_day for debit in ledger.debits()]
        assert days == ["2029-12-31", "2029-12-31", "2030-01-01"]


def test_debits_survive_reopen_and_refuse_clock_regression(tmp_path):
    from sentira.storage.quota import QuotaLedger

    path = tmp_path / "ledger.sqlite3"
    policy = small_policy(tmp_path)
    with QuotaLedger(path, policy, clock=Clock()) as ledger:
        first = ledger.debit("live", "videos.list")
        ledger.settle(first, ok=True)
        with pytest.raises(ValueError):
            ledger.settle(first, ok=False)
    with QuotaLedger(path, policy, clock=Clock(T0 - timedelta(seconds=1))) as reopened:
        assert [d.outcome for d in reopened.debits()] == ["ok"]
        with pytest.raises(ValueError, match="backwards"):
            reopened.debit("live", "videos.list")
        assert len(reopened.debits()) == 1
    other = small_policy(tmp_path, live=5999, buffer=501)
    with pytest.raises(ValueError, match="policy"):
        QuotaLedger(path, other, clock=Clock())


def test_failed_call_still_spends_units(tmp_path):
    from sentira.collectors.quota import MeteredClient
    from sentira.storage.quota import QuotaLedger

    with QuotaLedger(":memory:", small_policy(tmp_path), clock=Clock()) as ledger:
        transport = Transport(ledger, fail_on={1})
        with pytest.raises(RuntimeError):
            MeteredClient(transport, ledger).call("retrieval", "commentThreads.list", {})
        (debit,) = ledger.debits()
        assert debit.outcome == "failed" and debit.units == 1
        assert ledger.spent() == {"retrieval": 1}
