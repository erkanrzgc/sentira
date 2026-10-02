# Collection policy P: polling schedule and replay visibility

Status: authorised by the operator on 2 October 2026 as the first part of the
pilot preparation. It implements the schedule rules of the
[BACKTEST](../../BACKTEST.md) amendment and the replay rule of §0.3 for synthetic
inputs only. It adds no API client and no collection.

## Purpose

Live collection and historical replay must read the same policy object. The
schedule decides when a deployed collector would have polled a video; replay
decides when a retrieved thread would have become visible under that schedule.
Both are pure functions, so they can be tested exactly before any source
contract exists.

## Modules

| Module | Delivers |
|---|---|
| `config/collection.py` | The validated policy: discovery interval, poll ages, page size and page cap |
| `collectors/policy.py` | Discovery ticks, poll jobs for one video, nominal poll times and replay times |

The example `examples/synthetic-policy.toml` carries the proposed values of §0.3:
discovery every 6 hours, polls at ages 1 h, 6 h, 24 h, 72 h, 7 d and 30 d, and at
most 10 pages of 100 threads per poll. None of these values has been measured.

## Schedule

| Rule | Behaviour |
|---|---|
| Discovery ticks | Whole multiples of the interval from midnight UTC; the interval must divide a day |
| Discovery first | No job is due before discovery |
| Coalescing | Every pending age already due at discovery or at a restart is covered by one immediate job |
| Anchoring | Later ages stay at publication plus age, whatever the discovery delay |
| Restart | Completed ages are never scheduled again |
| Records | Each job keeps its covered ages, its due time and the ages it missed; actual delivery belongs to execution |
| Catch-up | A job due after the last registered age is marked live-only |

## Replay

A thread's replay time is the first nominal poll that would return it, plus the
job latency λ; it is undefined where no poll would return it. Nominal polls follow
the schedule with discovery at the first registered tick. Each poll lists threads
newest first and stops at the newest thread already seen or after the page cap,
so a thread behind the cap is never returned later.

| Assumption | Consequence |
|---|---|
| A thread is listable from its publication time | Not verified; provider indexing delay would make replay early |
| The stop is at the publication time of the newest thread already seen | A deleted last-seen thread would make a real collector page further; replay is then conservative |
| Equal publication times have an unknown provider order | Where the cap falls inside such a group, none of the group is admitted at that poll |
| Every thread on the video is supplied | Replay on survivors alone can admit threads that were behind the cap (the amendment's counterexample) |

## Deviations

| Phase 1 text | This increment | Reason |
|---|---|---|
| Replay checked against a recorded video | Checked against a synthetic provider with complete visibility history | No recorded responses exist; the synthetic provider and collector are written independently of the replay function |
| λ from the measured addendum | λ is an explicit argument | λ needs seven days of live running |
| Replay inside `storage/asof.py` | A pure function in `collectors/policy.py`, not yet wired into the reader | Wiring needs a replay-time column and an equivalence test, so the single read path is not duplicated |

## Acceptance tests

| Contract | Named test in `tests/collectors/test_policy.py` |
|---|---|
| The shipped policy validates; malformed policies are refused | `test_shipped_policy_validates`, `test_invalid_policies_are_refused` |
| Discovery follows the registered ticks | `test_discovery_follows_registered_ticks` |
| No poll before discovery | `test_no_poll_before_discovery` |
| Missed ages are coalesced at late discovery | `test_late_discovery_coalesces_missed_ages` |
| Later ages stay anchored to publication | `test_future_ages_anchored_to_publication` |
| A restart keeps completed ages | `test_restart_preserves_completed_jobs` |
| A catch-up after the last age is live-only; replay ignores it | `test_catch_up_after_last_age_is_live_only` |
| Threads behind the page cap are never replay-visible | `test_row_beyond_page_cap_never_replay_visible` |
| Threads after the last poll age are never replay-visible | `test_row_after_last_poll_age_never_replay_visible` |
| A tie at the page cap admits none of the tie | `test_tied_rows_at_page_cap_are_not_admitted` |
| Replay inputs are validated | `test_replay_inputs_are_validated` |
| Replay equals live visibility on complete synthetic histories | `test_replay_matches_live_visibility_on_synthetic_complete_history` |

Outside this increment: the cost projection, the pilot registration and the
end-to-end synthetic pilot run, which follow, and the API client, which waits
for the source decision.
