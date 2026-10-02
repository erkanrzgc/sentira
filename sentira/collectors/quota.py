"""The metered client: every call is debited in the quota ledger before it is made.

The transport is supplied by the caller; only synthetic transports exist. The order
is always debit, call, settle, so a call the ledger refuses never runs and a call
that fails stays spent.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sentira.storage.quota import QuotaExhausted, QuotaLedger


@dataclass(frozen=True, slots=True)
class DrainResult:
    completed: int
    # "quota_exhausted" when the ledger refused a request; None when all were served.
    stopped: str | None


class MeteredClient:
    def __init__(self, transport: Callable, ledger: QuotaLedger):
        if not callable(transport) or type(ledger) is not QuotaLedger:
            raise ValueError("A transport and a quota ledger are required")
        self._transport = transport
        self._ledger = ledger

    def call(self, purpose, endpoint, params):
        debit = self._ledger.debit(purpose, endpoint)
        try:
            result = self._transport(endpoint, params)
        except BaseException:
            self._ledger.settle(debit, ok=False)
            raise
        self._ledger.settle(debit, ok=True)
        return result


def drain(requests, client, sink):
    """Serve (purpose, endpoint, params) requests in order until the quota refuses one.

    Results are handed to the sink as they arrive, so everything collected before a
    refusal is kept. Exhaustion is a clean stop, not an error; transport failures
    still propagate.
    """
    if type(client) is not MeteredClient or not callable(sink):
        raise ValueError("A metered client and a sink are required")
    completed = 0
    for purpose, endpoint, params in requests:
        try:
            result = client.call(purpose, endpoint, params)
        except QuotaExhausted:
            return DrainResult(completed, "quota_exhausted")
        sink(result)
        completed += 1
    return DrainResult(completed, None)
