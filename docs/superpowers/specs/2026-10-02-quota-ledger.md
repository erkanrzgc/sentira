# Offline quota ledger and metered client

Status: authorised by the operator on 2 October 2026 as the next increment. It
implements the quota contract of [BACKTEST](../../BACKTEST.md) §B and §C with
synthetic transports only. It adds no API client, no credentials and no
collection; live data remains blocked by [SOURCE_USE](../../SOURCE_USE.md).

## Purpose

[AGENTS](../../../AGENTS.md) makes two collection rules binding: no endpoint outside
the registered set, and the quota ledger is debited before each call. Both can be
built and tested before any collector exists, so that the first adapter is
written against a ledger that already refuses what it must refuse.

## Modules

| Module | Delivers |
|---|---|
| `config/quota.py` | The validated quota policy: daily units, reservations, buffer purposes, quota-day offset, registered endpoints and unit costs |
| `storage/quota.py` | The persistent ledger: debits, outcomes and the per-pool spend of a quota day |
| `collectors/quota.py` | The metered client, debit then call then settle, and `drain`, which stops cleanly on exhaustion |

## Deviations from the Phase 1 map

| Phase 1 text | This increment | Reason |
|---|---|---|
| `collectors/quota.py` holds the persistent ledger | The ledger is in `storage/quota.py`; the client stays in `collectors/quota.py` | Only storage may import the database driver (`test_architecture.py`) |
| `quota_ledger` table in `storage/schema.py` | Two tables in a separate ledger file | The ledger is not document storage; each file refuses the other's schema |
| "Clean stop before exhaustion" | The ledger refuses the first call the remaining units cannot cover, before it is made | A call is never made on units the day does not have |
| Buffer for retry and re-poll overrun | Only purposes the policy names may draw on the buffer; the example names live collection only | Retrieval and survival absorb their own retries, so neither can consume the live safety margin |

## Policy

The policy is TOML, `mode = "synthetic"`, with unknown and missing fields
rejected. The reservations are exactly live, retrieval, survival and buffer;
each is a non-negative integer and together they equal `daily_units`. The
example follows the calculated reservation table in BACKTEST §B (6,000, 3,000,
500 and 500 units).

Only read-only list methods can be registered, each with a positive integer
cost. `search.list` is refused even when listed, because search draws on a
separate provider bucket and is excluded by design. The quota day is the calendar
day at a registered fixed offset from UTC, a multiple of 15 minutes. The
provider's actual reset time is not verified here; the offset is a registered
input that a live policy must state with its source.

A fixed offset cannot follow daylight saving. Where the provider's reset moves
between two offsets, a live policy registers the one with the later reset in UTC
(the more negative offset). The ledger day then never starts before the
provider's: for part of the year it closes up to an hour late, which can only
under-spend, never overspend.

## Ledger

| Rule | Behaviour |
|---|---|
| Order | `debit` writes a pending row before the transport runs; `settle` records `ok` or `failed` once |
| Pools | A debit draws on its purpose's reservation, then on the buffer if the policy names the purpose, and is refused with `QuotaExhausted` otherwise; nothing is written for a refusal |
| Spend | Pending, successful and failed debits all count; a crash between debit and call therefore errs towards spending |
| Atomicity | The reservation check and the debit row share one immediate transaction, so handles on one file read the same spend |
| Clock | The ledger owns its clock; a write earlier than the last write is refused |
| Policy | Every debit records the digest of the policy it was made under. Reopening under a new policy adopts it, and the day's spend so far counts against the new reservations; a new quota-day offset is refused, because days at two offsets overlap |
| Outcome | An outcome that cannot be recorded, for example after a clock step back during the call, leaves the debit pending; it still counts, and the call's result or error is returned unchanged |
| Validation | An unknown purpose or unregistered endpoint is refused before any row is written |

`drain` serves one purpose's requests in order and hands each result to a sink as
it arrives. One purpose per run means an exhausted reservation stops only its
own queue: retrieval running dry never holds back live collection. On exhaustion
it returns the number completed and `quota_exhausted`; everything already handed
to the sink stays with the caller, and durable storage of results belongs to
the sink. Transport failures still propagate, with the units spent and the
debit marked failed. Retry policy is not part of this increment.

## Acceptance tests

| Contract | Named test |
|---|---|
| The shipped policy carries the calculated reservations; search has no cost | `collectors/test_quota.py::test_shipped_policy_matches_the_calculated_reservations` |
| Invalid policies are refused (sum, extra pool, negative reservation, buffer purpose, search, malformed or write method, zero cost, no endpoints, live mode, offset) | `::test_policy_reservations_must_sum_to_daily_units` |
| The ledger is debited before the call | `::test_ledger_debited_before_call` |
| Ledger units equal the calls made, over 200 random calls with refusals and failures | `::test_ledger_units_equal_calls_made` |
| Exhaustion stops cleanly; the sink keeps the results, debits persist, and another purpose is still served | `::test_exhaustion_stops_cleanly_and_persists_collected` |
| `drain` reports completion when the quota suffices | `::test_drain_reports_completion_when_quota_suffices` |
| Retrieval and survival cannot spend the live reservation or the buffer | `::test_retrieval_cannot_spend_live_reservation` |
| Unregistered endpoints and purposes are refused before any debit | `::test_unregistered_endpoint_refused_before_any_debit` |
| The quota day turns over at the registered offset | `::test_quota_day_resets_at_registered_offset` |
| Debits survive reopening; settling twice and clock regression are refused | `::test_debits_survive_reopen_and_refuse_clock_regression` |
| A new policy keeps the day's spend and is recorded per debit; a new offset is refused | `::test_policy_change_keeps_the_days_spend` |
| An unrecordable outcome leaves the debit pending and spent, and does not replace the result or error | `::test_unrecorded_outcome_leaves_debit_pending_and_spent` |
| A failed call still spends its units | `::test_failed_call_still_spends_units` |
| Two handles on one file share one reservation | `storage/test_quota_ledger.py::test_two_handles_cannot_overspend_a_reservation` |
| A pending debit counts as spent after reopening | `::test_pending_debit_counts_as_spent_after_reopen` |
| Ledger and document storage refuse each other's files | `::test_ledger_refuses_a_foreign_database` |
| Settlement, purposes, policy and clock are validated | `::test_settle_and_inputs_are_validated` |

The two-handle test interleaves calls in one process; it shows that spend is read
from the file, not cached per handle. Parallel processes rely on SQLite's
immediate transactions and are not tested.

Outside this increment: the platform API client, credentials, the collection
policy *P*, retries, the `collect-live` command and live quota measurement.
