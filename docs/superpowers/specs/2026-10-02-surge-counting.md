# Offline surge registration and positive count

Status: authorised by the operator on 2 October 2026 as the next increment. It
implements a synthetic, offline subset of Phase 1 in [BACKTEST](../../BACKTEST.md)
and enables no collection. Live data remains blocked by [SOURCE_USE](../../SOURCE_USE.md).

## Purpose and order

Phase 1 asks whether the available history holds enough surges to evaluate
conditional growth. Its rule is that the surge definition exists, locked and
hashed, before a single episode is counted. The increment therefore proceeds in
dependency order:

| Step | Module | Delivers |
|---|---|---|
| 1 | `backtest/registration.py` | Validated surge definitions and a lock that counting verifies |
| 2 | `series/episodes.py` | Episodes, labels and censoring on a strict as-of series |
| 3 | `backtest/positives.py`, `count` command | Per-cell counts, the registered fallback and a stamped report |

The quota ledger and the scenario track follow separately.

## Deviations from the Phase 1 map

| Phase 1 text | This increment | Reason |
|---|---|---|
| YAML registration files | TOML | The runtime uses the standard library only; existing configuration is TOML |
| SHA-256 of both files | SHA-256 of the canonical validated content of each file | Line-ending conversion on checkout must not break a committed lock, while every definitional change still does |
| Local calendar day | Calendar day at a registered fixed UTC offset | No time-zone database is required; daylight-saving changes are not modelled |
| Measured addendum computed by registered rules | Supplied synthetic values for `c_min`, `k_floor` and `H` | Rule-based computation and the pre-origin refusal need retrieved history |
| Topic series from lexical assignment, raw and cleaned | One supplied raw series per topic | Topic assignment and integrity screens are later modules |
| Replay-visible rows | Strict observation-time visibility only | Replay needs complete recorded visibility histories |

Fixtures live in `examples/` and declare `mode = "synthetic"`. They are not the
confirmatory registration v1, which is locked only after a pilot.

## Registration and lock

The registration also fixes the walk-forward constants of §A.5: the history
start *D*0 at a local midnight, a burn-in of at least the baseline window, a
training span and the test fold length. The first origin *O*1 = *D*0 + burn-in +
training is derived, never supplied; with the synthetic values it is *D*0 + 118
days. A counted series must start at *D*0.

The registration fixes the §A.3 definitions: baseline days, trailing window,
refractory period, end rule, maximum duration in horizons, the grid of onset
multipliers *m*, size multipliers κ and horizons *H*, the primary cell, the two
fallback size multipliers, *K*min, the reporting floor and the week floor. The
measured addendum names its registration version and supplies `c_min`, `k_floor`
and a horizon from the grid. Unknown fields, missing fields, cells outside the grid
and inconsistent floors are rejected.

The lock records both content digests and is created with exclusive creation.
Loading a locked registration recomputes both digests and refuses any mismatch.
Every count report is stamped with both digests.

## Episodes

Input is a sequence of rows with a publication time and a visibility time, an
evaluation span and the grid cells to evaluate. At each hourly tick *t*, only rows
visible by *t* are read, through `VisibilityCursor` in `storage/asof.py`. The cursor
applies the same predicate as `AsOfReader`, and an equivalence test keeps the two
implementations aligned, so there is one visibility rule. One pass over the ticks
serves every cell. Definitions follow §A.2–A.3:

- **Baseline:** the median daily count over the registered number of whole calendar days before the current day, as visible at *t*.
- **Onset:** the trailing count reaches *m* times the baseline and `c_min`, no episode is open, and the refractory period has passed. The daily baseline is scaled to the trailing window (*b* × trailing hours / 24) before it is compared with a trailing count. The baseline is frozen at onset as *b*\*.
- **Size and threshold:** size is net excess over *b*\*. *k* = max(κ·*b*\*, `k_floor`). τ_k is the first tick with size ≥ *k*.
- **At τ_k:** overshoot is size(τ_k)/*k*. An episode already at 2*k* is labelled detected at crossing: its crossing time is τ_k, no later crossing is recorded, and it is excluded from the T1 population.
- **Labels:** positive or negative is resolved at τ_k + *H* for both classes; a later resolution than the end of data is censored, not negative. An episode that ends without reaching *k* is below *k*; one still open at the end of data without reaching *k* is open, not below *k*.
- **Interpretation:** an episode's size stops at its end, so a 2*k* crossing counts only while the episode is open. A renewed surge after the end is a new episode, subject to the refractory period.
- **End:** the trailing count stays below the **current** baseline for the registered quiet period, or the maximum duration elapses.

## Count report

Counts per cell and span: episodes, eligible (reached *k*), positive, negative,
censored, detected at crossing, and the share of eligible episodes where `k_floor`
binds. An eligible episode belongs to the span and fold containing its τ_k; other
episodes belong by onset. The pre-origin span [*D*0, *O*1) is never a test fold:
its counts are reported separately and never enter *K*min or the week floor. The selected cell
follows the registered rule. The primary cell is used when both classes reach
*K*min; otherwise the fallback for the short class is used. With both classes
short, the outcome is "not backtestable on current history". The week floor
counts distinct test folds, ⌊(τ_k − *O*1) / fold⌋, that contain a positive. Every figure is labelled
*calculated*; the report is marked synthetic and carries no accuracy claim.

## Acceptance tests

| Contract | Named test |
|---|---|
| Shipped synthetic registration and lock validate | `backtest/test_registration.py::test_shipped_synthetic_registration_validates` |
| Unknown or missing fields rejected | `::test_unknown_or_missing_fields_rejected` |
| Primary and fallback cells lie in the grid | `::test_primary_and_fallback_cells_must_be_in_grid` |
| An existing lock is never overwritten | `::test_lock_refuses_to_overwrite` |
| A changed registration or addendum is refused | `::test_modified_registration_refused_after_lock`, `::test_modified_measured_addendum_refused_after_lock` |
| τ_k is the first as-of tick at *k* | `series/test_episodes.py::test_tk_is_first_tick_at_which_asof_series_reaches_k` |
| Rows invisible at *T* cannot change episodes known at *T* | `::test_onset_invariant_to_rows_invisible_at_T` |
| Detected-at-crossing episodes leave the T1 population | `::test_detected_at_crossing_excluded_from_t1_population` |
| Unresolved horizons are censored | `::test_unresolved_horizon_is_censored_not_negative` |
| Both classes resolve at τ_k + *H* | `::test_resolution_time_is_tk_plus_H_for_both_classes` |
| A level shift ends by the current baseline or maximum duration | `::test_level_shift_does_not_extend_episode_past_max_duration` |
| Counting refuses a changed registration | `backtest/test_positives.py::test_count_refuses_on_registration_hash_mismatch` |
| Counts match a hand-labelled fixture | `::test_counts_match_hand_labelled_fixture` |
| Fallback follows the registered rule | `::test_fallback_cell_chosen_by_registered_rule` |
| The week floor is enforced | `::test_week_floor_enforced` |
| *O*1 is derived from registered constants | `backtest/test_registration.py::test_first_origin_is_registered_constant` |
| Only test-fold episodes enter the selection | `backtest/test_positives.py::test_positives_counted_only_in_test_folds` |
| Weeks are registered folds, not calendar weeks | `::test_week_floor_uses_registered_folds` |
| A series must start at *D*0 | `::test_count_refuses_series_not_starting_at_history_start` |

Outside this increment: collectors, the quota ledger, topic assignment, integrity
screens, half-life and horizon computation, survival, walk-forward evaluation and
any accuracy figure.
