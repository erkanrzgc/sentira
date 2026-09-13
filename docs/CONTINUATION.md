# Continuation record

Updated 2026-09-13. The user approved [IMPLEMENTATION_START](IMPLEMENTATION_START.md).
The current increment is an offline foundation, not the complete Phase 1.

## Implemented contracts

| Contract | Code | Named evidence under `tests/` |
|---|---|---|
| Frozen documents; no identifier/counter fields outside the declared contract | `core/document.py` | `core/test_document.py::test_document_has_no_raw_identifier_or_counter_field`, `::test_document_is_frozen`, `::test_unknown_fields_rejected_without_echoing_values` |
| Every document and storage column has one field class | `core/document.py`, `storage/schema.py` | `core/test_document.py::test_every_field_declares_exactly_one_class`, `storage/test_schema.py::test_schema_has_no_raw_identifier_or_document_counter_columns` |
| HMAC-SHA256 and platform/entity separation | `core/identity.py` | `core/test_identity.py::test_hash_matches_independent_hmac_vector`, `::test_platform_and_identifier_kind_are_separated` |
| Parent references retain comment identity | `core/identity.py` | `core/test_identity.py::test_parent_reference_resolves_to_comment_hash` |
| Missing key fails; diagnostics exclude key/raw inputs | `core/identity.py` | `core/test_identity.py::test_missing_key_fails_at_startup`, `::test_secret_and_raw_identifier_not_in_diagnostics` |
| Target types restricted at loading and direct construction | `config/schema.py` | `config/test_schema.py::test_target_of_disallowed_type_rejected_at_load`, `::test_direct_target_constructor_enforces_types` |
| Storage-owned observation clock; first observation preserved | `storage/repository.py` | `storage/test_repository.py::test_observed_at_cannot_be_supplied_by_caller`, `::test_first_observation_wins_on_reingest` |
| Atomic writes and recoverable failure | `storage/repository.py` | `storage/test_repository.py::test_failed_write_rolls_back_document_and_snapshots`, `::test_rollback_preserves_previous_data` |
| Strict reads do not admit later observations | `storage/asof.py` | `storage/test_asof.py::test_visibility_includes_exact_T_but_not_one_microsecond_earlier`, `::test_snapshot_observed_after_T_never_read`, `::test_mutating_and_deleting_invisible_rows_does_not_change_past` |
| Observation/edit metadata excluded from feature output | `storage/asof.py` | `storage/test_asof.py::test_results_do_not_expose_observation_metadata_to_features` |
| Database-driver imports confined to storage | Package boundary | `test_architecture.py::test_only_storage_imports_database_driver` |
| Synthetic boundary to persisted strict view | Whole offline slice | `test_offline_e2e.py::test_synthetic_boundary_to_strict_read_end_to_end` |

Identity namespaces distinguish authors and comments. `PARENT` is an alias of
`COMMENT`: a reference must hash to the same identity as the comment it identifies.
Hashes use JSON-framed platform, entity kind and identifier with HMAC-SHA256.
The key is exactly 32 bytes; environment encoding is 64 hexadecimal characters.

## Verification

Local environment: Python 3.12.10 on Windows. Runtime has no third-party
dependencies; development versions are pinned in `requirements-dev.txt`.
The commands in the README reproduce the checks. The implementation plan records
the red/green sequence; initial contract runs failed because the implementation
modules did not yet exist. A separate failing parent-reference regression exposed
and corrected an incorrect identity namespace before integration.

Measured on the final worktree run: **95 tests passed**, **94.99% statement and
branch coverage combined**, with Ruff lint and format checks passing. Editable
package installation succeeded. These are software checks, not model accuracy.

The work was fast-forwarded into the local main checkout and reverified there:
95 tests passed, combined coverage remained 94.99%, and lint/format checks passed.
The project-local `.venv` is ready to run the README commands. No push or release
was performed.

Independent review identified a duplicate-ingestion clock-watermark defect. The
new regression first failed, then passed after a transactional `write_state` table
was added. The reviewer rechecked both clock regression and rollback across reopen;
no additional actionable finding was reported in that fix. `write_state` contains
provenance only and is not visible to the feature reader.

## Operational limits

- Only synthetic provenance exists in the input enum. It is a caller declaration,
  not an automatic detector of personal data. No real ingestion entry point exists.
- Missing keys fail at construction of the hashing boundary. Internal storage
  accepts already-hashed documents without independently requiring an environment
  key; no complete collector-startup guarantee is claimed.
- Hash shape validation cannot prove that an identifier was produced with the
  authorised key. The tested boundary is the HMAC helper and synthetic end-to-end
  path; no API collector has been implemented or tested.
- `AsOfReader` returns internal feature inputs, including hashed authors and text;
  it is not a client reporting API. There is no person-query method or external API.
- The database is local, single-threaded per repository instance and disposable.
  It stores first-seen synthetic text without a production refresh/deletion system.
  Snapshot conflicts at the same document/time/metric fail atomically.
- No historical replay, quota ledger, scheduling, registration execution, topic
  classification, integrity screening, language model or numerical forecast exists.
  A separate synthetic scenario report is implemented as described below.
- No retention, backup expiry, output suppression, text redaction or client access
  control has been implemented. Do not use this foundation to store real content.
- Numerical pilot budgets, output suppression thresholds and real entity evidence
  remain to be registered before their respective features are enabled.

## Synthetic briefing increment

The detailed scenario design and sample were approved on 2026-09-13. The offline
implementation now loads four TOML configuration files and fictional evidence,
registers them in a separate SQLite ledger and renders all three domains through
one Markdown pipeline. The README contains the runnable command.

Configuration and evidence are immutable validated records. Unknown fields,
unregistered references, mismatched origins, ambiguous timestamps and changed
question definitions under an existing identifier fail. Support and revision
cycles fail; mutual contradictions are permitted. Observation belongs to storage;
the CLI supplies an explicit simulation clock and uses an ephemeral ledger.

The single evidence view excludes later observations and expired records. Later
writes do not change earlier reports. Registration must itself have been observed
by the cutoff. The ledger preserves first observation and advances its monotonic
write watermark even for unchanged duplicate batches. Writes and registration
roll back together on validation failure.

The report records the configuration digest, source attribution, content digests,
publication/observation/expiry times, counterevidence, missing sources, stale
records, scenario triggers and review dates. Repeated origins count once.
Corroboration cannot be promoted by an unavailable or same-origin supporting
record. Unsupported scenario text is withheld. Markdown and HTML text are escaped.

### Verification of the briefing increment

Measured in the isolated implementation checkout: **147 tests passed**, including
52 briefing tests; combined statement and branch coverage **93.21%**. Ruff lint
and formatting passed. Editable installation succeeded and two separate CLI runs
produced byte-identical Markdown files (SHA-256
`0a3dddc8fb1f82e98c15eecbd54eeedcd243e388e998c2bbf6dd394bcc2b49af`).
These figures describe software verification, not forecasting accuracy.

Independent review reproduced two defects: a view admitted sources outside its
selected registration, and a multi-domain claim could borrow corroboration from
only one domain. Both regression tests failed before the fixes and passed after
them. The reviewer independently reran all 52 briefing tests and found no further
material issue in the recheck. Views now filter against the selected source
registration. Every reference must cover all domains of its parent claim; split
claims by domain when their evidence differs.

### Limits specific to this increment

- All claims and links are fictional. Rights references are synthetic identifiers,
  not verified permissions. Domain and attribution text is operator supplied;
  this is not a semantic detector of personal information or institutional status.
- Expiry is a cutoff visibility simulation, not physical deletion or suppression
  of already exported reports. Production lifecycle controls are still absent.
- Scenario drafts are operator-authored. The program checks support references;
  it does not establish whether their meaning entails a scenario or contradicts it.
- The CLI starts a new ledger each run. Persistent question locking is available
  through the storage API; immutable report issuance and outcome scoring are deferred.
- Missing coverage describes fixture availability. There are no live fetch attempts,
  collection-success claims, automatic resolutions or forecast probabilities.

## Next bounded work

Review the generated fictional report for usefulness before adding live sources.
Numerical forecasting and a downloaded local model remain separate later work.
The existing production-readiness work remains necessary:

1. Resolve source-use conditions in SOURCE_USE alongside a concrete lifecycle
   design. Determine what can be stored, refreshed, deleted and reproduced.
2. Specify a fixed small pilot sample, quota ceiling, schedule and separate pilot
   registration. Implement deterministic scheduler/quota logic against sanitised
   recorded responses only when the source contract is ready.
3. Start real collection only after lifecycle controls, source-use acceptance and
   credentials are in place. Do not substitute a model demonstration for this gate.
4. Build an independent human evaluation set before selecting a teacher/student.
   Report aggregate distribution error as well as classification metrics.

The existing forecasting research remains useful, but survivor-only reconstruction
must not be promoted to confirmatory evidence. No accuracy figure or live quota
measurement was produced by this offline increment.
