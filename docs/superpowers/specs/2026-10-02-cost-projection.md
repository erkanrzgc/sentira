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
| `config/volume.py` | Validated volume assumptions: channels, videos per channel-day, thread strata (share of videos and threads per video), cumulative thread share by poll age, playlist page size and the reported playlist item ceiling |
| `collectors/cost.py` | `project` and a deterministic Markdown report |
| `cost` command | `--policy`, `--quota`, `--volume`, `--output`, with `--overwrite` required to replace a report |

## Rules

| Item | Rule |
|---|---|
| Discovery | Channels × discovery ticks per day × playlist pages per tick, at least one page per channel and tick |
| Polls | The poll jobs of the registered schedule, averaged over every publication minute of one discovery interval, so coalescing counts exactly as the collector runs it |
| Strata | Each thread stratum is costed on its own and weighted by its share of videos, because pages and the page cap are not linear in threads; a mean alone understates a heavy tail |
| Poll pages | New threads since the previous job, from the cumulative share at the job's last age. The first poll reads until the listing ends, at least one page; a later poll stops on the thread it saw before, so it reads one page past its whole pages of new threads. Never more than the page cap |
| Lost threads | New threads beyond the page cap at a poll, reported per day |
| Unpolled threads | Threads published after the last poll age are never observed live and are reported per day |
| Playlist ceiling | History reachable per channel at the reported, unverified 20,000-item ceiling; a warning where a history-year exceeds it |
| Live total | Discovery plus polls, compared with the live reservation; an overrun is stated, and the buffer is never counted |
| Retrieval | Every thread of a history-year's videos, at least one page each, plus playlist enumeration; days per history-year at the retrieval reservation, rounded up with exact integer arithmetic |
| Survival and buffer | Reservations shown; survival is not projected until strata are designed |
| Unit costs | Read from the quota policy, so an endpoint missing from the registered set stops the projection |

Shares are registered at poll ages only. A coalesced job is costed at the share of
its last covered age, which slightly overstates the threads of a job that ran
before that age's time; this errs towards cost.

## Example

With the fictional assumptions in `examples/synthetic-volume.toml` (60 channels, 10
videos per channel-day, one stratum of 300 threads per video), live collection
needs 240 discovery units and 3,600 poll units, 3,840 in all, within the
6,000-unit live reservation. A history-year costs 661,380 units: 220.46 days at
3,000 units a day, which BACKTEST §B gives as about 220 days and the projection
rounds up to 221, because a partial day still has to be spent. Both are calculated
from assumptions. A single stratum is a simplification: with 5% of videos at
5,000 threads, the tail alone loses 37,500 threads a day to the page cap.

## Acceptance tests

| Contract | Named test in `tests/collectors/test_cost.py` |
|---|---|
| The example reproduces the documented arithmetic | `test_shipped_projection_matches_documented_arithmetic` |
| Polls follow the registered schedule, including coalescing | `test_projection_uses_the_registered_schedule` |
| Every call costs a page, even with nothing new | `test_every_call_costs_a_page_even_when_nothing_is_new` |
| A later poll reads one page past its new threads | `test_later_polls_read_one_page_past_their_new_threads` |
| A heavy tail is costed by stratum, not by its mean | `test_heavy_tail_is_costed_by_stratum_not_by_mean` |
| Threads after the last poll age are reported | `test_threads_after_the_last_poll_age_are_reported` |
| The playlist ceiling warns when a history-year is unreachable | `test_playlist_ceiling_warns_when_a_history_year_is_unreachable` |
| Day counts use exact ceiling division | `test_ceiling_division_is_exact_for_large_values` |
| The page cap bounds cost and lost threads are reported | `test_page_cap_bounds_poll_cost_and_reports_lost_threads` |
| A live overrun is stated, not hidden | `test_live_overrun_is_reported_not_hidden` |
| A missing retrieval reservation is stated | `test_missing_retrieval_reservation_is_reported` |
| Invalid assumptions are refused | `test_invalid_volume_assumptions_are_refused` |
| One share per poll age | `test_shares_must_match_poll_ages` |
| The report is deterministic, labelled and stamped | `test_report_labels_every_figure_calculated` |
| The command writes once and needs `--overwrite` to replace | `test_cost_command_writes_report_and_refuses_overwrite` |

Outside this increment: measured cost from the ledger, disk cost, survival strata
and the pilot registration, which comes next.
