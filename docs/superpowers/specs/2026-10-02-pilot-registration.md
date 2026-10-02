# Pilot registration and lock

Status: authorised by the operator on 2 October 2026 as the third part of the
pilot preparation. It implements the pilot registration of
[BACKTEST](../../BACKTEST.md) §A.9 and the registration order of the amendment for
synthetic inputs. No pilot is run and no collection is enabled; the values in the
example are fictional and are not the pilot budget a live pilot must register.

## Purpose

The pilot sizes the history the main registration can afford. Its own rules must
therefore be fixed before it collects anything, or the pilot could be tuned on
what it sees. The lock makes that order checkable: it cannot be written after
collection starts, and it stops matching as soon as the pilot, the collection
policy, the quota policy or the volume assumptions change.

## Registration

| Field | Rule |
|---|---|
| `registered_at`, `collection_start` | Registration precedes collection |
| `history_days` | 1–90: the bounded history span retrieved, ending at collection start |
| `live_days` | 7–60: the job latency needs at least seven days of live running |
| `quota_ceiling_units` | A hard ceiling for the whole pilot |
| `adaptations` | Only adaptations named in code: replacing an unreachable channel within its stratum, and shortening the history span to the ceiling. Any other is refused |
| `[selection]` | `seeded_random` with a registered seed |
| `[[strata]]` | Name, channel type and number of channels; at most 60 channels in all |

Unknown fields are refused everywhere, so the schema has no place for a counter:
a stratum or selection cannot be defined by audience size, views or engagement.

## Lock

The lock is JSON written with exclusive creation. It records the digests of the
pilot, collection policy, quota policy and volume assumptions, the lock time and
the projected pilot cost. Loading recomputes all four digests and the projection.

| Rule | Behaviour |
|---|---|
| Order | A lock time after collection start is refused |
| Cost | The projection of the cost step, with the pilot's channel count, gives live units per day × live days plus the history span's share of a history-year's retrieval, rounded up. A projection above the ceiling is refused |
| Integrity | A changed input file, a changed projection, a changed lock time or an unknown lock field is refused |

For the example (12 channels, 14 live days, 28 history days) the projection is
768 × 14 + 10,148 = 20,900 units, within a ceiling of 30,000 (*calculated*).

## Deviations

| Phase 1 text | This increment | Reason |
|---|---|---|
| `config/pilot.yaml` | TOML, with a JSON lock | The runtime uses the standard library; other registrations are TOML |
| Pilot fields: sample, strata, schedule, quota ceiling, span, adaptations | Also the volume assumptions' digest and a projected cost | A ceiling is only meaningful against the assumptions the pilot was sized with |
| Pilot data excluded from confirmatory test folds | Not yet enforced | Exclusion needs the main registration to reference the pilot lock; it belongs to the v1 step |

## Acceptance tests

| Contract | Named test in `tests/backtest/test_pilot.py` |
|---|---|
| The example validates and its lock verifies byte for byte | `test_shipped_pilot_validates_and_lock_verifies` |
| No field can hold a counter | `test_selection_schema_has_no_place_for_a_counter` |
| Invalid pilots are refused | `test_invalid_pilots_are_refused` |
| Unregistered adaptations are refused | `test_unknown_adaptation_refused` |
| The live run covers latency measurement | `test_live_days_cover_latency_measurement` |
| No lock after collection starts | `test_pilot_lock_refused_after_collection_start` |
| No lock above the ceiling | `test_pilot_lock_refuses_projected_cost_above_ceiling` |
| Any changed input is refused | `test_changed_policy_quota_or_volume_refused_after_lock` |
| A tampered lock record is refused | `test_tampered_lock_record_refused` |
| A lock is never replaced | `test_pilot_lock_never_overwritten` |
| The `lock-pilot` command | `test_lock_pilot_command` |

Next: an end-to-end synthetic pilot run that refuses to start without a valid lock
and stops at the ceiling.
