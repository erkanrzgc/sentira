# Quota cost projection

Status: authorised by the operator on 2 October 2026 as the second part of the
pilot preparation. It turns the quota arithmetic of [FEASIBILITY](../../FEASIBILITY.md)
and [BACKTEST](../../BACKTEST.md) §B into tested code. Every figure it produces is
*calculated*; the inputs that matter most remain unmeasured (BACKTEST §D.1–D.2).

## Purpose

The reservation table was arithmetic written by hand. The pilot must be sized
against what the reservations actually buy, and the realised cost of policy *P*
must later be compared with a projection made by the same rules. A projection in
code, read from the registered policy and quota files, makes that comparison
possible and keeps the arithmetic from drifting away from the schedule.

## Modules and command

| Item | Delivers |
|---|---|
| `config/volume.py` | Validated volume assumptions: channels, videos per channel-day, threads per video, cumulative thread share by poll age, playlist page size |
| `collectors/cost.py` | `project` and a deterministic Markdown report |
| `cost` command | `--policy`, `--quota`, `--volume`, `--output`, with `--overwrite` required to replace a report |

## Rules

| Item | Rule |
|---|---|
| Discovery | Channels × discovery ticks per day × playlist pages per tick, at least one page per channel and tick |
| Polls | The poll jobs of the registered schedule, averaged over every publication minute of one discovery interval, so coalescing counts exactly as the collector runs it |
| Poll pages | New threads since the previous job, from the cumulative share at the job's last age; at least one page, at most the page cap |
| Lost threads | New threads beyond the page cap at a poll, reported per day |
| Live total | Discovery plus polls, compared with the live reservation; an overrun is stated, and the buffer is never counted |
| Retrieval | Every thread of a history-year's videos, at least one page each, plus playlist enumeration; days per history-year at the retrieval reservation, rounded up |
| Survival and buffer | Reservations shown; survival is not projected until strata are designed |
| Unit costs | Read from the quota policy, so an endpoint missing from the registered set stops the projection |

Shares are registered at poll ages only. A coalesced job is costed at the share of
its last covered age, which slightly overstates the threads of a job that ran
before that age's time; this errs towards cost.

## Example

With the fictional assumptions in `examples/synthetic-volume.toml` (60 channels, 10
videos per channel-day, 300 threads per video), live collection needs 240 discovery
units and 3,600 poll units, 3,840 in all, within the 6,000-unit live reservation. A
history-year costs 661,380 units, or 221 days of retrieval. These agree with the
hand arithmetic in BACKTEST §B; both are calculated from assumptions.

## Acceptance tests

| Contract | Named test in `tests/collectors/test_cost.py` |
|---|---|
| The example reproduces the documented arithmetic | `test_shipped_projection_matches_documented_arithmetic` |
| Polls follow the registered schedule, including coalescing | `test_projection_uses_the_registered_schedule` |
| Every call costs a page, even with nothing new | `test_every_call_costs_a_page_even_when_nothing_is_new` |
| The page cap bounds cost and lost threads are reported | `test_page_cap_bounds_poll_cost_and_reports_lost_threads` |
| A live overrun is stated, not hidden | `test_live_overrun_is_reported_not_hidden` |
| A missing retrieval reservation is stated | `test_missing_retrieval_reservation_is_reported` |
| Invalid assumptions are refused | `test_invalid_volume_assumptions_are_refused` |
| One share per poll age | `test_shares_must_match_poll_ages` |
| The report is deterministic, labelled and stamped | `test_report_labels_every_figure_calculated` |
| The command writes once and needs `--overwrite` to replace | `test_cost_command_writes_report_and_refuses_overwrite` |

Outside this increment: measured cost from the ledger, disk cost, survival strata
and the pilot registration, which comes next.
