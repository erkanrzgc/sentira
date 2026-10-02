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
| `[selection]` | `seeded_random` with a registered seed and the version of the frozen channel frame it draws from |
| `[[strata]]` | Name, channel type and number of channels; one stratum per channel type, at most 60 channels in all |

Unknown fields are refused everywhere, so the schema has no place for a counter:
a stratum or selection cannot be defined by audience size, views or engagement.

## Channel frame and sample

`config/channels.py` loads the frozen channel frame: identifiers, channel types
and the time each channel was added, in one canonical order. For each stratum the
sample is drawn by `random.Random(f"{seed}:{stratum}")` from the frame's channels
of that type that were present at registration, so a channel added later can never
enter it. A stratum with fewer candidates than it registers is refused. The drawn
sample is written into the lock and recomputed on loading.

## Lock

The lock is JSON written with exclusive creation, creating its directory if
needed. It records the digests of the pilot, channel frame, collection policy,
quota policy, volume assumptions and topic taxonomy, the drawn sample, the lock
time with its source, and the projected pilot cost. Loading recomputes all of
them, with strict types. The taxonomy digest was added by the topic-taxonomy
review, which raised the lock schema to 2.

| Rule | Behaviour |
|---|---|
| Order | The lock time must lie between registration and collection start |
| Taxonomy | The taxonomy must be frozen at or before the lock time, so no topic is written after the pilot has seen data |
| Time source | Without `--locked-at` the system clock is used and recorded as `system`; a typed time is recorded as `declared`. A declared time is a statement, not evidence of order: a live pilot must use the system clock and anchor the lock outside the repository before collection |
| Cost | With the pilot's channel count, live units per day × live days plus the retrieval of exactly the history span (every thread page and each channel's playlist pages, at least one each). A projection above the ceiling is refused |
| Integrity | A changed input file, sample, projection, lock time or time source, a value of the wrong type or an unknown lock field is refused |

For the example (12 channels, 14 live days, 28 history days) the projection is
768 × 14 + 3,360 × 3 + 12 × 6 = 20,904 units, within a ceiling of 30,000
(*calculated*).

## Deviations

| Phase 1 text | This increment | Reason |
|---|---|---|
| `config/pilot.yaml` | TOML, with a JSON lock | The runtime uses the standard library; other registrations are TOML |
| Pilot fields: sample, strata, schedule, quota ceiling, span, adaptations | Also the channel frame, the volume assumptions' digest, the drawn sample and a projected cost | A seed alone does not fix a sample, and a ceiling is only meaningful against the assumptions the pilot was sized with |
| Locked before collection | Checked against the recorded lock time; offline, that time may be declared | No trusted clock exists offline; the time source is recorded so a declared time is never mistaken for evidence |
| Pilot data excluded from confirmatory test folds | Not yet enforced | Exclusion needs the main registration to reference the pilot lock; it belongs to the v1 step |

## Acceptance tests

| Contract | Named test in `tests/backtest/test_pilot.py` |
|---|---|
| The example validates and its lock verifies byte for byte | `test_shipped_pilot_validates_and_lock_verifies` |
| The sample is fixed by seed and frame | `test_sample_is_fixed_by_seed_and_frozen_frame` |
| A channel added after registration is never sampled | `test_channel_added_after_registration_is_never_sampled` |
| A stratum needs enough candidates from the registered frame | `test_stratum_needs_enough_candidates` |
| No field can hold a counter | `test_selection_schema_has_no_place_for_a_counter` |
| Invalid pilots are refused | `test_invalid_pilots_are_refused` |
| Unregistered adaptations are refused | `test_unknown_adaptation_refused` |
| The live run covers latency measurement | `test_live_days_cover_latency_measurement` |
| The lock lies between registration and collection start | `test_pilot_lock_window_runs_from_registration_to_collection_start` |
| No lock above the ceiling | `test_pilot_lock_refuses_projected_cost_above_ceiling` |
| No lock before the taxonomy is frozen | `test_pilot_lock_binds_a_taxonomy_frozen_before_it` |
| Any changed input is refused | `test_changed_input_refused_after_lock` |
| A tampered lock record is refused | `test_tampered_lock_record_refused` |
| A lock is never replaced | `test_pilot_lock_never_overwritten` |
| The `lock-pilot` command, its time source and output directory | `test_lock_pilot_command` |
| The channel frame is canonical, counter-free and dated | `config/test_channels.py::test_shipped_frame_validates_in_canonical_order`, `::test_file_order_does_not_change_the_digest`, `::test_invalid_frames_are_refused` |

Next: an end-to-end synthetic pilot run that refuses to start without a valid lock
and stops at the ceiling.
