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
- No historical replay, scheduling, topic classification, integrity screening,
  language model or numerical forecast exists. Later sections add a locked
  synthetic surge registration with counts and a quota ledger with synthetic
  transports only. A separate synthetic scenario report is implemented as
  described below.
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

The increment was fast-forwarded into local main and reverified: 147 tests,
93.21% combined coverage, clean Ruff lint/format and identical example output.
The generated worktree was removed. No push or release was performed.

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

The operator accepted the fictional report and subsequently prioritised data and
manual evaluation over model selection. The local analyst design is deferred.
See [DATA_PILOT](DATA_PILOT.md) for source qualification, the proposed 18-case
worksheet and review rubric. Concrete source research remains outside the repository.
Three source-grounded development reading drafts were prepared privately on
2026-09-14. They contain original short summaries and source links, not retained
source packets. They remain unreviewed by a human and ineligible for scored replay:
observation precision is date-only and source-use qualification remains unresolved. Numerical forecasting and
a downloaded local model remain separate later work.
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

## Latest data-first progress, 2026-09-14

The first reading drafts distinguish timetable adoption from outcomes, legislative
adoption from publication, and a diplomatic announcement from an agreement. They
are assistant-authored development material, not human ground truth. No real
evidence was inserted into the synthetic ledger. Automated source access, retention
and redistribution remain unqualified. A primary-law search failed with a tool
connection error; no legal conclusion was inferred. The next operator action is
to review these drafts while access and lifecycle qualification proceeds.

## Adversarial check, 2026-09-14

See [ADVERSARIAL_REVIEW](ADVERSARIAL_REVIEW.md). Four new synthetic checks
initially returned three passes and one failure: a visible correction does not
withhold a scenario using the earlier claim. The failing expectation remains a
strict expected failure, not a resolved guarantee. Full suite: 150 passed and
one expected failure; targeted Ruff checks passed. No production code changed.
Revision-aware scenario review is now the immediate correctness task.


## Revision eligibility fix, 2026-09-17

The previously recorded expected failure is resolved. Storage supplies cutoff-bound
review identifiers for revised evidence and dependent support, including when a
correction has expired. The renderer withholds affected scenario prose and does
not silently replace frozen references. Historical reports remain unchanged;
unaffected scenarios still render. See
[revision design](superpowers/specs/2026-09-17-revision-review.md) for limits.

Measured: 158 tests passed; no expected failures; combined coverage 93.38%; Ruff
lint and format passed. Independent review found no material gating defect;
additional prose and transitive-dependency regressions passed. No live ingestion,
model or source-use permission was added. Real lifecycle controls remain separate.

## Offline procedural case register, 2026-09-25

The operator approved the bounded case-register design. A separate `case-report`
command now renders original synthetic TOML fixtures with explicit case IDs,
institutional decision references, source/page links, event dates and supplied
UTC observation times. Location relations distinguish adjacent reference areas
from affected footprints. Reporting labels and all case facts remain external.

The sole cutoff selector excludes later observations. Missing closure and
objection records remain gaps; elapsed display durations never resolve them.
Visible supersession marks affected cases for review and retains the superseded
record, without automatically declaring a replacement legal status. Unknown
fields, invalid references and supersession cycles are rejected. The existing
three-domain briefing command remains separate.

Measured in the implementation checkout: 200 tests passed, including 42 new case
checks; combined statement/branch coverage 93.46%; Ruff lint and format passed.
Two CLI executions produced identical output (SHA-256
`a1f9428a329c0ac440cba7c95902e9b948f19062dac640578b917ffd95c450c5`).
Independent review found double-encoding of existing URL escapes. A failing
regression reproduced it, the fix passed, and the reviewer confirmed resolution.

See [design](superpowers/specs/2026-09-25-case-register-design.md),
[implementation plan](superpowers/plans/2026-09-25-case-register.md) and
[fixture](../examples/synthetic-cases.toml). Run the README example to inspect
output. These are software checks, not semantic or forecasting accuracy.

Limits: no model, OCR, network access, automatic stage extraction, persistent
observation capture, immutable report issuance or real-data ingestion. The
synthetic flag is an input contract, not a semantic privacy detector. Cases are
operator-authored snapshots; changing supplied historical metadata changes the
report. Production collection still requires source-use and lifecycle work.

Next bounded work: operator review of the example report, then broaden manual
cases beyond a single publisher and document format. Define human-reviewed
reference labels and simple-rule baselines before evaluating local models.

## Adversarial case checks and review boundary, 2026-09-25

Thirteen additional synthetic checks exercise the existing implementation:
calendar-month wording without day conversion, exact cutoff inclusion and
microsecond exclusion, equivalent timezone observations, future display notices,
transitive and competing supersessions, empty evidence, malformed collections,
and distinct publication/event dates. No runtime behaviour changed. These are
regression guards for existing contracts, not fixes for reproduced failures.

Measured: 213 tests passed; combined statement/branch coverage 94.25%; Ruff lint
and format passed. The case subset contains 55 checks. Neither coverage nor
passing synthetic tests establishes semantic accuracy on real documents.

Private manual research now includes three planning cases and a twelve-question
development worksheet with assistant-drafted references. No question has human
reference approval, no model answers were collected and no score was computed.
The operator is not expected to supply specialist document verification; their
feedback concerns clarity and usefulness. Qualified source review and source-use
decisions remain prerequisites for a real-data model evaluation. The worksheet
must not be promoted to independent ground truth or a held-out test set.

## Source qualification, 2026-09-26

Private documentation review identified a municipal open-data portal with a
published attribution licence and documented anonymous location services.
Dataset pages provide supporting geographic context, not planning decisions or
evidence of future designation changes. No operational API call or dataset
ingestion was performed, and no source-use acceptance was recorded.

The publisher's terms and FAQ disagree about preservation of earlier dataset
versions. Historical availability therefore remains unverified. Catalogue
modification dates must not be treated as event dates or historical observations.
Resource-specific conditions, request budgets and lifecycle handling remain open.

Next: prioritise a documented decision or display-notice source that answers the
procedural question directly. Supporting location feeds do not justify expanding
the implementation scope. Runtime code and the previously recorded test results
are unchanged; tests were not rerun for this documentation-only update.

Manual browser research subsequently reached a direct municipal planning notice.
The page distinguishes council decision, approval and display dates, and links
to a drawing and report. Those linked contents and the original decision were
not inspected in this increment. A published display-end date and a current
not-on-display label do not establish objection outcomes or legal finality.

The new private development case has no independent reference approval. Public
interface access establishes neither a documented collector API nor reuse rights.
The separate open-data portal licence does not automatically cover this source.
Next: cross-check the linked report, preserving distinct procedural dates; any
new schema representation of approval requires design and named tests first.

## Linked report cross-check, 2026-09-26

The linked private report was subsequently retrieved and relevant pages visually
checked. Its subject and scales agree with the notice, but exact text searches
did not independently match the notice's identifier and later procedural dates.
This does not establish absence from images or differently formatted text.

The report includes a residential proposal; its conservation title alone must
not cause that evidence to be omitted. Separate sections give different area
totals, and one percentage does not match ordinary rounding of the stated areas.
The private record preserves both values, scope labels, page references and
calculated checks without choosing an authoritative total. Construction conditions
are stated but their fulfilment is unverified. No current entitlement is inferred.

Next evidence target: original decision/approval material and subsequent changes
or objection outcomes. No model score, independent label approval, collector or
runtime change was added. Documentation whitespace checks passed; software tests
were not rerun for these research notes.

## Published decision cross-check, 2026-09-26

The authority's published council decision and embedded committee text were
read directly. Date, subject and locality match the private notice case; the
decision heading uses a shorter reference rendering, retained alongside the
notice's reference. The record distinguishes proposal, committee referral,
committee consideration and council acceptance for onward transmission to a
conservation authority. That acceptance does not establish the later authority's
decision or fulfilment of construction conditions.

An archive row reuses the short decision number in another year. Matching by
number alone is therefore insufficient; date, issuing institution and subject
must remain part of manual verification. Other cases' objection outcomes must
not be attached to this case. Its later objection outcome remains unverified.

Next: retrieve the intervening conservation decision and reconcile any conditions
or revisions against the report. This is research evidence, not a new implemented
matching guarantee. No runtime code or model evaluation changed.

## Conservation archive leads, 2026-09-26

Official agenda entries supplied a shared file reference and candidate decision
dates/numbers for a matching locality and planning subject. They narrow the next
retrieval target but do not establish exact case identity or the decisions'
operative effect. No approval event was inferred from agenda inclusion or from
a populated decision-number column. The operative texts remain unverified.

A linked drawing transfer was interrupted; its partial rendering is explicitly
excluded from evidence and evaluation. Private research records the bounded
search coverage and retrieval failures. Next: retrieve the candidate decisions,
then match their scope and conditions to the notice and report. Runtime code,
source-use gates and independent evaluation status remain unchanged.

The relevant monthly registration listings were subsequently inspected without
finding the sought operative decisions. Their coverage is not established as
exhaustive. A bounded drawing retry also timed out and remains excluded from
evidence. Repeating the same search or transfer is not the next useful action.
A private concise case brief now consolidates supported statements, numerical
differences and unresolved status. Future work should use a different official
publication route or a separately authorised document request for the missing
decision texts. No external request was sent; no code or evaluation changed.

## Prepared document request, 2026-09-26

The authority's published contact page was retrieved. A private, unsent request
now specifies the candidate file, decision references, releasable annexes and
later replacement decisions, and asks for evidence of the case match. It contains
no operator identity. A published email address does not establish the formal
admissibility of an information request.

The response checklist separates receipt time from document dates, checks the
operative text and annex versions, and does not infer reuse permission from
document access. Sending remains subject to explicit user authorisation. No
external communication occurred. The private case synthesis is available now;
missing decisions remain evidence gaps, not inferred approvals or rejections.

## Fourth-case review worksheet, 2026-09-26

The private planning worksheet now has an eight-question extension derived from
the existing fourth-case research notes. It covers council versus later approval
stages, agenda versus operative decision text, conflicting area values, percentage
arithmetic, display closure versus finality, observation-time leakage, repeated
origins and a useful answer that preserves both the residential proposal and gaps.
External sources were not retrieved again while preparing this extension.

Calculated inventory: twelve earlier questions plus eight new questions gives
twenty questions across four development cases. These are not twenty independent
cases and do not complete the separate three-domain pilot. Human-approved
references remain absent; no model answers, scores or review durations exist.

Questions, assistant-drafted answers and structured review fields are separate
private files. Their manifest records local byte hashes, not source-use acceptance,
an eligible evidence packet or a frozen scoring registration. The earlier packet
was preserved and its recorded hashes checked. Partial drawings and missing
operative decisions remain excluded. The extension is explicitly ineligible for
training, scoring and historical replay; publication dates were not substituted
for observation times.

Next: source-qualified reference review and genuinely observed review effort,
before selecting a model task. Document retrieval can proceed through a different
official route or a separately authorised request. No external communication or
runtime change was made in this increment.

## Input failure handling and file protection, 2026-09-26

Three reproduced defects were corrected within the existing offline contracts.
List or table values in briefing domain/status fields previously raised an
uncaught type error. These fields now validate their string contract before set
membership. UTC conversions outside the representable calendar range now raise
a validation error rather than an uncaught overflow. Both changes preserve the
CLI's controlled failure path and existing output.

The briefing command previously compared resolved output with unresolved
configuration filenames. A configuration file linked to a Markdown destination
could therefore be overwritten with a generated report. Each configuration input
is now resolved before the output-alias check. This is protection for the supplied
paths at validation time, not a guarantee against concurrent filesystem changes.

| Named regression test | Verified contract |
| --- | --- |
| `tests/briefing/test_cli.py::test_cli_rejects_non_text_enums_without_exposing_input` | Six malformed enum inputs fail without echoing their values or replacing output |
| `tests/briefing/test_cli.py::test_cli_never_overwrites_symlinked_configuration` | A linked configuration target cannot become the report destination |
| `tests/core/test_document.py::test_utc_rejects_unrepresentable_conversion` | Both calendar boundaries produce a validation error |
| `tests/cases/test_cli.py::test_case_cli_rejects_unrepresentable_utc_without_overwriting` | Invalid conversions leave the existing report intact |

Measured: all eleven new parameter cases failed before their corresponding fixes;
the full suite then passed 224 tests with 94.42% combined statement/branch coverage.
The symbolic-link test ran without a skip on this host. Ruff lint and format
checks passed for 58 files after formatting. Both CLI examples were generated
twice in separate processes and produced identical bytes for identical inputs.

An exploratory sweep applied 330 field/type mutations across the configuration,
evidence and case loaders; none raised an unexpected exception type. This is a
bounded exception-handling check, not an exhaustive input proof or semantic
accuracy measurement. No source access, model run, real-data ingestion or external
communication was introduced. Example output remains explicitly synthetic.

## Complete suppression of unsupported scenario prose, 2026-09-27

The renderer previously withheld the title and summary of a scenario with
ineligible support but still printed its registered unknowns and strengthening
or weakening triggers. This contradicted the report's statement that substantive
scenario text was withheld and the insufficient-evidence rule in SCENARIO_DESIGN.
The same support-eligibility gate now applies to those remaining prose fields.
Question metadata, support and counterevidence references, and evidence gaps
remain visible. This does not hide the underlying attributed evidence records.

Named regression: `tests/briefing/test_adversarial.py::test_unavailable_support_withholds_all_scenario_text`.
Its insufficient, stale and expired cases each failed before the fix and passed
afterwards; each also checks that an unaffected scenario and its trigger survive.
Measured: 227 tests passed, combined statement/branch coverage 94.42%, Ruff lint
and format checks passed. A separate static review found no actionable issues;
the reviewer did not independently rerun tests.

Four local synthetic demonstrations exercise fresh, insufficient, stale and
expired evidence using external configuration and evidence files. Their manifest
records command arguments and file hashes for repetition. Calculated output counts:
the fresh example has four scenario headings and eight trigger lines; each other
example has zero of both while retaining insufficient-evidence and gap messages.
These are rendering checks, not analytical accuracy or independent reference labels.

## Order-independent validation of long dependencies, 2026-09-27

A synthetic chain of 1,200 evidence records exposed order-dependent validation:
the dependency-first ordering loaded, but the opposite ordering exceeded Python's
recursive call limit. Long cyclic input also raised an uncaught recursion error
instead of the specified validation error. Dependency validation now uses an
iterative traversal of support and revision edges. Contradiction edges remain
outside the acyclicity requirement; shared and duplicate-role edges remain valid.

Named checks in `tests/briefing/test_pipeline.py`:

- `test_long_dependency_chain_is_independent_of_input_order`: support, revision
  and mixed chains in both orders load all records.
- `test_long_cycle_rejection_preserves_ledger_and_clock`: rejected cycles leave
  earlier report bytes, visible records and the storage clock unchanged; a later
  valid write remains possible.
- `test_shared_support_and_revision_target_are_not_a_cycle`: converging support
  and a reference serving both support and revision roles do not produce a false
  cycle finding.

Measured: the initial long-chain checks produced six failures and three passes
before the fix. The completed suite passed 237 tests with 94.45% combined
statement/branch coverage; Ruff lint and format passed for 58 files. A separate
static review found no actionable issues and did not independently rerun tests.
This is a bounded synthetic robustness check, not a production throughput result.
The correction-review propagation algorithm and database format are unchanged.

## Source-level development review, 2026-09-27

Eight fourth-case questions were checked against published decision text, a
notice, two agenda PDFs and the existing local report. Initial research-tool
failures were preserved separately from successful browser and bounded document
retrieval. Relevant agenda rows were visually inspected. The local report was
not downloaded again; unchanged local bytes do not establish current remote
version identity. Earlier date-only observations were not rewritten.

The review clarified a temporal interpretation: a report's earlier statement
that no approved plan existed does not by itself contradict a later approval
notice. Operative decision texts, exact case linkage and approved-version identity
remain unresolved. A display-status label from an earlier review was not treated
as freshly verified when the retrieved detail page showed only dates.

Tool-clock observations bounded the source pass; the calculated elapsed interval
was 114 seconds, including assistant reading, tool latency and retrieval recovery,
excluding later note writing. Human review time, operator usefulness and time
savings remain unmeasured. One assisted pass does not establish a recurring
bottleneck or justify model training. The private structured audit preserves
pending human review and ineligibility for scoring and training. No external
communication or runtime change occurred; software tests were not rerun for this
research-only update.

## Consolidated development readiness and PDF availability, 2026-09-27

The first three cases received a bounded visual recheck of five previously
rendered pages. A private register combines those twelve questions with the
eight fourth-case review records, preserving twenty unique questions across four
development cases. All human review fields remain pending, all model responses
absent, and scoring/training eligibility false. Unreviewed pages and unresolved
later procedural outcomes are explicitly outside the findings.

One attribution gap was identified: a question comparing two publications named
only one source in its original structured record. The consolidated record now
references both; earlier drafts and their recorded hashes were preserved.

A local PDF text-availability probe covered four existing files. Calculated
inventory: 76 pages, of which nine returned zero non-whitespace characters from
the extractor. Four of those nine pages were visually inspected and contain
meaningful notice or decision text. The other five zero-text pages were not
visually classified. Nonzero extracted text is not proof of complete extraction.
Current remote versions were not retrieved for this probe.

This supports a bounded candidate experiment comparing local OCR with ordinary
PDF text extraction on original synthetic scans. The experiment, its independent
references and acceptance criteria are not implemented or approved by this note.
No OCR accuracy, human effort saving or model benefit was measured. Missing
operative documents still require retrieval and cannot be supplied by inference.
No runtime change was made; checks covered record references, review flags and
preservation of the earlier private packet hashes.

## Local OCR preflight and proposed experiment, 2026-09-27

A local executable check measured Tesseract version 5.5.2. Its recognition-data
listing contained only `osd`, which supplies orientation/script detection rather
than the text-recognition data required for the proposed run. The private
preflight record retains the executable digest and command outputs. Recognition
status is `not_run_missing_recognition_data`; accuracy and human effort remain
unmeasured. No data installation, OCR execution or network request occurred.

The proposed bounded design is recorded in
[the offline OCR experiment](superpowers/specs/2026-09-27-offline-ocr-experiment.md).
It compares text extraction and local OCR across four original fictional
document families in two representations. Authoring values stay in external
configuration. Inputs, matching rules and baselines must be locked before any
scoring; missing data must not be reported as zero accuracy. This document is
an experiment proposal, not an implemented runtime capability.

Next work is to finalise the fixture/matching registration and recognition-data
provenance before running the synthetic comparison. Independent human review,
source-use acceptance and lifecycle controls remain unresolved product gates.
This update changes documentation only; software tests were not rerun.

## Synthetic OCR experiment implemented and exercised, 2026-09-27

The bounded experiment is now implemented under `experiments/ocr/`, outside the
installed package and existing CLI. `prepare`, `lock` and `compare` author original
fictional PDF pairs, bind inputs and tools to a registration, then retain native
outputs and exact field comparisons. TOML holds all document content and engine
settings. No real-document ingestion or case-ledger integration was added.

The earlier missing-data preflight was resolved by a separate download from the
official recognition-data repository at a pinned revision. The licence text and
file digests were recorded. Data remains in ignored experiment output; no system
installation, hosted inference or training occurred. The general analyst-model
decision remains deferred.

Two independently locked development runs used the same four authored families:
clean pages at 150 dpi with 16-point type, then a predeclared stress condition at
72 dpi with 10-point type. The assistant inspected every rendered page before
locking. This was not independent human review. **Calculated exact-field counts:**
clean image-only OCR 16/16, stress image-only OCR 7/16; majority 6/16 and seeded
random 7/16 for both. Ordinary image-only PDF extraction returned 0/16 in each
run. See [all results and limitations](../experiments/ocr/RESULTS.md).

The stress run produced plausible wrong dates, a missing reference zero and
label/scale failures. It did not exceed the random baseline. No rules were
changed to repair the score. Neither successful process exit nor clean-template
success justifies automatic acceptance into evidence. Per-page elapsed process
times are measured; human correction time and time savings are unmeasured.

Verification: 293 tests passed, including 56 experiment tests. Installed-package
statement/branch coverage remains 94.45%; that figure excludes `experiments/`.
Ruff lint and formatting passed. Native PDF/OCR calls were exercised separately
on the local synthetic fixtures, not in tests. Independent static review found
two issues, both fixed with regressions: unreadable native bytes now remain
preserved and unscored, and changed runtime versions are refused before output.

Named experiment checks cover exact digits and units, ambiguous labels, input
and registration tampering, outside symlinks, running-code/runtime drift, missing
recognition data, partial timeout output, unreadable UTF-8, failed-page
denominators, visual-review acknowledgement and preservation of existing output.
No semantic privacy filter or complete native dependency fingerprint is claimed.

Next: specify source-page-linked field review and abstention before any integration
of OCR with case reports. Representative varied-layout evaluation, independent
human references, source-use acceptance and lifecycle controls remain open.

## Explicit synthetic field review, 2026-09-28

`experiments/field_review/` now creates a source-linked review packet and applies
external TOML decisions. Packets include registered image digests and OCR
candidates but exclude authoring answers and baselines. Every field defaults to
pending; accepting, correcting or withholding a value requires an explicit
decision. Corrections require a supplied value and reason, never an answer lookup.

Decision bindings cover the packet, registration and result bytes. Source image
changes fail the existing registration check; changed results invalidate earlier
decisions. Missing, ambiguous or failed recognition cannot be accepted. Reports
retain every field and suppress pending/withheld values. Existing output is never
silently replaced. This is not reviewer authentication or proof of correctness.

The recorded stress output produced a 32-field packet: eight paired pages times
four fields, not 32 independent cases. With empty decisions, all 32 remained
pending with no approved values. A separately labelled **simulated** demonstration
corrected one date, accepted one duration and withheld one scale; 29 fields stayed
pending. Exactly those two explicit values appeared in the structured report.
No independent human evaluation, true-reference label or time saving is claimed.

| Contract | Named test in `tests/experiments/` |
| --- | --- |
| Exclude answer keys and suppress unreviewed candidates | `test_field_review.py::test_packet_excludes_answers_and_pending_report_suppresses_candidates` |
| Preserve explicit corrections and omitted gaps | `test_field_review.py::test_explicit_correction_never_uses_expected_and_retains_omissions` |
| Reject acceptance of unusable recognition | `test_field_review.py::test_unusable_candidate_cannot_be_accepted` |
| Invalidate changed inputs | `test_field_review.py::test_digest_binding_covers_results_and_packet`; `::test_tampered_source_is_rejected` |
| Reject duplicate/unknown decisions | `test_field_review.py::test_malformed_or_duplicate_decisions_fail` |
| Preserve existing output | `test_field_review_cli.py::test_packet_command_never_replaces_existing_output` |

Verification: 336 tests passed, including 43 new field-review checks. Ruff lint and
format passed. Installed-package statement/branch coverage remains 94.45% and
does not include experimental modules. An independent reviewer reran all 43
field-review tests and found no substantive issue. Both original OCR experiment
locks and their recorded environments still validated; this increment did not
alter those runner files or rerun OCR.

Local demonstrations are in `out/field-review-packet-v1`,
`out/field-review-pending-v1` and `out/field-review-simulated-v1` in the attached
worktree. The packet digest is
`df2d5424fe8c832363f5e333db535e56a52e4fa78bc6bb88c39bb3d15f336107`.
The structured report also records the exact TOML decision-file digest.

The OCR and review commands remain separate synthetic experiments. Case-ledger
integration, persistent review history, authenticated review, calibrated
abstention and representative independent evaluation are not implemented.
Next work should define which reviewed field types may become evidence and how
later source revisions withdraw that eligibility before any automatic hand-off.
Live-source permissions, lifecycle controls and the analyst-model gate remain
unchanged.

## Revision-aware synthetic candidate eligibility, 2026-09-28

`experiments/eligibility/` rebuilds the locked field-review packet, reapplies
external decisions and checks an external source-version context at a cutoff.
Only explicitly reviewed, permitted and structurally valid fields can appear as
`eligible_candidate`. This is a candidate list, not a case-event hand-off.

A changed source version requires fresh review even if its bytes revert to the
old digest. Unavailable and withdrawn sources suppress values. Valid future
observations do not change earlier output. Review times and source observation
times remain operator-authored synthetic simulation inputs, not a trusted clock
or persistent review history. The reviewed and latest visible version/image
digest pairs are explicitly distinguished.

The existing stress packet and simulated decisions were reused without rerunning
OCR. Calculated from the emitted rows: the early view retained 29 pending fields,
one withheld field and two eligible candidates. After one simulated source-page
revision, all four fields on that page required review and the other 28 remained
pending. No values survived the later view; replacement values were not inferred.
These are software demonstration counts, not independent evaluation scores.

| Contract | Named test in `tests/experiments/` |
| --- | --- |
| Future observations preserve earlier output; changed/reverted versions invalidate review; version/digest pairs stay distinct | `test_eligibility.py::test_future_observation_invariance_and_changed_then_reverted_requires_review` |
| Withdrawn or unavailable sources suppress values | `test_eligibility.py::test_source_status_suppresses_values` |
| Future review, pending, withheld and unpermitted fields remain gaps | `test_eligibility.py::test_pre_review_is_invisible_and_pending_withheld_not_permitted_remain_gaps` |
| Invalid calendar dates and malformed fields are not repaired | `test_eligibility.py::test_invalid_values_are_not_repaired` |
| Exact character and calendar-month preservation | `test_eligibility.py::test_valid_candidates_preserve_all_characters_and_json_timestamps` |
| Reject malformed context and mismatched review bindings | `test_eligibility.py::test_malformed_context_and_wrong_binding_raise_value_error` |
| Preserve prior output and record exact input hashes | `test_eligibility_cli.py::test_existing_output_is_preserved`; `::test_exact_input_hashes_and_report_written` |

The bounded offline chain now reaches reviewed-field candidate eligibility.
Independent human references and correction-time measurements remain absent.
Further product acceptance needs those observations; repeated runs over these
same authored pages cannot supply them. Do not infer forecasting ability or start
model training from this demonstration. Event semantics, authenticated review,
persistent source lifecycle controls and live-source permission remain separate
unimplemented requirements.

Verification: 384 tests passed, including 48 eligibility checks; Ruff lint and
format passed. Independent review found two provenance issues, both corrected:
reviewed/latest version-digest pairs are now separate, and all four raw input-file
digests are retained alongside canonical packet/decision digests. The reviewer
reran the 48 focused checks and found no remaining blocker in this bounded scope.
The previously measured installed-package coverage excludes experiments; no new
experiment coverage percentage is claimed.

Final local demonstrations are `out/eligibility-early-v2` and
`out/eligibility-later-v2`, using `out/eligibility-context-v1.toml`, in the attached
worktree. Earlier `v1` output remains preserved but predates the final complete
input-hash reporting. Original OCR and field-review artefacts remain intact.

## Local synthetic review screen, 2026-09-29

`experiments/review_screen/` generates a standalone `index.html` from the locked
OCR fixtures and result file. The generated page embeds source images and the
answer-free review packet. Source bytes are rechecked before output. All fields
start pending; explicit decisions export to the existing digest-bound TOML
contract. No server, model or live collector is added.

The page includes source navigation, image zoom and correction/withholding forms.
An optional start/pause timer exports active visible browser-session milliseconds
separately. This is not measured correction effort, authenticated human review
or evidence of time savings. Browser memory is transient; refresh loses edits.

Verification: 392 Python tests passed with no skips in this environment; the
separate Node suite passed two decision/timer tests. Ruff lint and format passed.
Independent review reran eight new Python checks and the two Node checks. An
export regression for an identifier containing DEL was corrected: the character
is escaped in TOML rather than emitted literally. Tests also cover quotes,
backslashes, Unicode, pending omission, image tampering after packet creation,
non-PNG input, script-termination escaping and preserving existing output.

| Contract | Named test |
| --- | --- |
| Answer-free packet binding, embedded images and injection escaping | `tests/experiments/test_review_screen.py::test_standalone_packet_binding_images_and_injection` |
| Fresh output and source integrity | `tests/experiments/test_review_screen.py::test_fresh_directory_and_tampering_leave_no_output` |
| Export compatible with Python review validation | `tests/experiments/test_review_screen.py::test_javascript_toml_round_trip` |
| Invalid decisions block export | `tests/experiments/review_screen.test.cjs`: `pending omitted; invalid acceptance and correction refused` |
| Hidden-page time requires explicit restart | `tests/experiments/review_screen.test.cjs`: `timer counts only explicitly active visible session; hidden requires restart` |

The final local demonstration is `out/review-screen-v2/index.html` in the attached
worktree. Its eight embedded source images and 32 packet fields were checked
against the original image and packet digests. Earlier `v1` output is preserved.
These are generated-artifact checks, not a visual inspection.

**Open verification:** browser tooling refused the local `file://` URL under its
security policy and explicitly prohibited workaround access. No browser rendering,
click, download or visibility-event smoke test was completed. The source and
export/timer unit tests cannot establish those UI behaviours. A person must open
the generated page locally, check layout/navigation, download an explicit review
and run the existing Python report validator before calling the screen usable.
Do not rerun unchanged tests or generate more pages to imply this gate has passed.
Independent human labels, representative evaluation and source-use gates remain
open; no model training or real collection follows from this screen.

## User-assisted screen hand-off, 2026-09-30

The user supplied screenshots showing the local page, source image, an accepted
decision reference and a corrected date, followed by the downloaded decision
TOML. The existing Python report command validated the original packet binding
and produced one accepted field, one corrected field and 30 pending gaps. The
accepted reference is `004.018/0081`; the corrected date is `2030-02-08`.
The exact downloaded file digest matches the generated report provenance.

The report and an unchanged copy of the submitted decisions are preserved in
ignored `out/user-assisted-review-v1/` in the attached worktree. User-entered
reason text remains in those local artefacts, not published documentation.
This closes the narrow displayed-page, accept/correct and download-to-validator
hand-off check. The assistant guided both decisions, so this is not independent
human reference labelling or a quality score. No session timing was submitted.
Page navigation, withholding, timer visibility events and broader browser/layout
coverage remain unverified. The earlier browser-tool restriction remains in force.

## Review-screen application-event checks, 2026-09-30

The separate Node suite now executes the real application and model scripts
against a small explicit DOM/event test double. Named checks in
`tests/experiments/review_screen_app.test.cjs` cover correction/reason retention
across pages, returning a field to pending, disabled acceptance for unusable OCR,
invalid drafts on other pages blocking export, withholding payloads, visibility
pause with explicit restart and unload warnings after edits. In-memory mutations
that remove restoration or disconnect the visibility listener are detected.

These tests capture Blob contents and invoke registered callbacks with controlled
time. They do not render images, parse HTML as a browser, deliver native browser
events, enforce native select behaviour or verify real download/dialog handling.
Consequently, remaining browser verification is not closed by this increment.
No production behaviour changed and no new human evaluation was performed.

A static template contract also checks each scaffold ID appears exactly once;
missing and duplicated attributes are rejected in negative test cases. This is
not an HTML parser. Verification: 392 Python tests and 10 combined Node tests
passed; Ruff lint and format passed. Independent review confirmed the application
tests exercise actual callbacks and state retention with explicit mock limits.

## Linux checks, continuous integration and audit fixes, 2026-10-02

The offline checks now run on Linux with an explicitly named Python 3.12
interpreter, and `.github/workflows/ci.yml` runs the same pinned commands on every
push and pull request: tests with branch coverage, Ruff lint and format, and the
two Node.js review-screen suites. Measured on the first workflow run: all steps
passed on the hosted Linux runner.

A full audit of the package and experiments then found one medium and several
low-severity defects. Each fix below first failed its named regression test.

| Named regression test | Verified contract |
| --- | --- |
| `tests/briefing/test_pipeline.py::test_apostrophe_renders_without_broken_entity` | Apostrophes render literally; no `&#x27;` entity text in briefings |
| `tests/cases/test_cases.py::test_case_report_renders_apostrophe_verbatim` | The same rule holds in case reports, which share the escaper |
| `tests/experiments/test_field_review.py::test_report_renders_apostrophe_verbatim` | The field-review report escaper, also used by eligibility reports |
| `tests/cases/test_cases.py::test_event_url_must_match_registered_source_host` | A case event link must share the host of its registered source |
| `tests/experiments/test_ocr_runner.py::test_lock_rejects_escaping_file_without_writing_lock` | An escaping registered name is refused before any lock file is written |
| `tests/experiments/test_ocr_runner.py::test_engine_error_with_invalid_utf8_keeps_engine_error` | Undecodable output from a failed run stays an engine error |
| `tests/experiments/test_review_screen.py::test_template_slots_filled_once` | Each template slot is filled once; inserted scripts are never rescanned |
| `tests/experiments/review_screen.test.cjs`: `unpaired surrogates are refused before export` | Text the Python TOML validator would reject is refused in the browser |
| `tests/experiments/review_screen_app.test.cjs`: `a successful download clears the unload warning until the next edit` | No unload warning after a successful export; a later edit restores it |
| `tests/experiments/review_screen_app.test.cjs`: `a valid download clears a stale error message` | Previously untested: the export's own error reset |
| `tests/experiments/review_screen_app.test.cjs`: `pagehide pauses a running timer` | Previously untested: the pagehide listener, with a mutation check |

The apostrophe defect was visible in the shipped synthetic briefing, where
`A's` rendered as entity text. Changing `experiments/ocr/run.py` changes its
registered code digest, so previously locked OCR fixtures must be registered
again before `compare` accepts them; this is the intended lock behaviour.

Measured: 399 Python tests passed with 94.47% combined statement and branch
coverage; 14 Node tests passed; Ruff lint and format passed for 89 files. Both CLI
examples were regenerated without error.

An assistant-run browser smoke test opened a generated review screen for a
two-page synthetic fixture in headless Chromium over a local HTTP server. Measured:
24 of 24 scripted checks passed, covering page navigation, retained decisions,
zoom, a blocked invalid export, a valid download, the timer, a 390-pixel layout
without horizontal overflow and the unload warning after a post-download edit. The
downloaded decisions passed the existing Python report validator. The script is
not committed and cannot be repeated from this repository. The visibility-event
pause was not exercised in the browser, and the check is not human evaluation.

Not changed: the name `decisions_sha256` still denotes two different digests in
the field-review output and the eligibility context, as the eligibility README
explains, and export errors do not yet name the affected field.

## Locked synthetic surge registration, 2026-10-02

First step of the [surge-counting increment](superpowers/specs/2026-10-02-surge-counting.md).
`sentira/backtest/registration.py` validates a synthetic registration of the
§A.3 surge definitions and a measured addendum, both TOML under `examples/`.
`write_lock` records the SHA-256 of each file's canonical validated content with
exclusive creation; `load_locked` recomputes both and refuses any mismatch.
Comments and line endings do not change a digest; every definitional change does.
The addendum values are supplied, not computed by registered rules.

| Named test in `tests/backtest/test_registration.py` | Verified contract |
| --- | --- |
| `test_shipped_synthetic_registration_validates` | The shipped files match the shipped lock; primary cell and 36-cell grid |
| `test_unknown_or_missing_fields_rejected` | Ten malformed registrations fail validation |
| `test_primary_and_fallback_cells_must_be_in_grid` | Six cross-file or grid violations write no lock |
| `test_lock_refuses_to_overwrite` | An existing lock is never replaced |
| `test_modified_registration_refused_after_lock` | A changed definition is refused after locking |
| `test_modified_measured_addendum_refused_after_lock` | A changed addendum is refused after locking |
| `test_lock_ignores_comments_and_line_endings_but_not_definitions` | Converted line endings and comments keep the lock valid |
| `test_unreadable_or_foreign_lock_refused` | Unreadable or foreign lock files are refused |

Measured: 423 Python tests passed with 95% combined statement and branch coverage;
Ruff lint and format passed. All new registration tests failed before the module
existed. No episode is counted yet; counting is the third step.

## Surge episodes on strict as-of synthetic series, 2026-10-02

Second step of the surge-counting increment. `sentira/series/episodes.py` is a
pure function over rows with publication and visibility times, a locked
registration and one grid cell. At each hourly tick it reads only rows visible by
that tick and applies the §A.2–A.3 definitions: whole-day baseline after a
burn-in, onset, frozen *b*\*, net excess, *k* with the `k_floor` flag, τ_k,
overshoot, detected-at-crossing, labels resolved at τ_k + *H*, censoring, the
current-baseline end rule, the refractory period and the maximum duration.

| Named test in `tests/series/test_episodes.py` | Verified contract |
| --- | --- |
| `test_tk_is_first_tick_at_which_asof_series_reaches_k` | τ_k is the first as-of tick at *k*; delayed rows move it later, never earlier |
| `test_onset_invariant_to_rows_invisible_at_T` | Deleting, delaying or adding rows invisible at *T* leaves three cells unchanged |
| `test_detected_at_crossing_excluded_from_t1_population` | A lump arriving at 2*k* is flagged and excluded from T1 |
| `test_unresolved_horizon_is_censored_not_negative` | One hour short of τ_k + *H* is censored; at τ_k + *H* it is negative |
| `test_resolution_time_is_tk_plus_H_for_both_classes` | Positive and negative both resolve at τ_k + *H*; an earlier crossing does not |
| `test_level_shift_does_not_extend_episode_past_max_duration` | A permanent level shift ends at 2*H* |
| `test_episode_ends_after_quiet_period_below_current_baseline` | A quiet day ends an episode before 2*H* |
| `test_end_rule_uses_current_not_frozen_baseline` | A count above *b*\* but below the current median ends the episode |
| `test_no_onset_during_refractory_period` | No episode opens within the refractory period |
| `test_detection_requires_locked_registration_grid_cell_and_hour_bounds` | Unlocked input, off-grid cells and unaligned bounds are refused |

Expected ticks are hand-computed from zero or piecewise-constant synthetic
backgrounds. Measured: six deliberate code mutations were tried (ignoring
visibility, a frozen end baseline, no refractory period, censoring by crossing,
no `c_min`, no maximum duration); every one now fails at least one test, after
the refractory test was added for the one that initially survived. 433 Python
tests passed with 95% combined coverage; Ruff passed.

With a zero baseline the quiet end rule cannot fire, because no count is below
zero; such episodes end at the maximum duration. This follows the registered
definition and is recorded here rather than changed.

## Per-cell surge counts and the count command, 2026-10-02

Third step of the surge-counting increment. `sentira/series/synthetic.py` expands
compact synthetic segments into rows; `sentira/backtest/positives.py` counts every
registered grid cell, applies the registered primary-and-fallback rule with
*K*min and the week floor, and renders a synthetic report stamped with both
registration digests and the series digest. The `count` command verifies the lock
before it reads the series.

| Named test | Verified contract |
| --- | --- |
| `tests/backtest/test_positives.py::test_counts_match_hand_labelled_fixture` | Four hand-labelled episodes: one each positive, negative, censored and detected at crossing |
| `::test_fallback_cell_chosen_by_registered_rule` | Primary, both fallbacks, both-short and fallback-short outcomes; no other cell is promoted |
| `::test_week_floor_enforced` | 19 weeks with a positive fail and 20 pass |
| `::test_count_refuses_on_registration_hash_mismatch` | A changed registration or addendum writes no report and echoes no input |
| `tests/backtest/test_cli.py::test_count_cli_renders_stamped_report` | The report carries both digests, one row per grid cell and no probability |
| `::test_count_cli_is_deterministic` | Identical inputs produce identical bytes |
| `::test_count_cli_protects_existing_output_and_inputs` | No overwrite without `--overwrite`; inputs and non-Markdown targets refused |
| `::test_count_cli_rejects_invalid_series` | Four malformed series fail without output |
| `tests/series/test_episodes.py::test_baseline_includes_late_rows_for_past_days` | A late row for a past day updates the baseline at the tick it becomes visible |

The new count tests failed at collection before `positives.py` existed. The
baseline is now cached until the local day changes or a late row for a past day
arrives; this cut one example run from 3.1 to 0.7 seconds (measured, single run)
with byte-identical output, and the late-row test was added after a deliberately
stale cache initially passed every test.

The fictional example reports "not backtestable on current history": at the
primary cell it has 2 positives and 1 negative against a *K*min of 100 per class.
This is a property of a small fixture, not a feasibility finding. Measured: 445
Python tests and 14 Node tests passed, 95% combined statement and branch coverage,
Ruff lint and format passed for 100 files.

## Review fixes for the surge-counting increment, 2026-10-02

A high-effort review of `3c7ec2d..14e76a7` produced ten findings, two reproduced on
the shipped fixtures. Eight are fixed here; counting outside test folds and the
calendar of the week floor need registered origins and are the next step.

| Named test | Verified contract |
| --- | --- |
| `tests/storage/test_asof.py::test_cursor_and_reader_agree_on_visibility` | The in-memory `VisibilityCursor` and `AsOfReader` admit the same 120 synthetic rows at every checkpoint, including exact observation times; the cursor refuses to move backwards |
| `tests/series/test_episodes.py::test_detected_at_crossing_excluded_from_t1_population` | A lump at 2*k* is labelled detected at crossing with its crossing at τ_k; no later crossing is invented |
| `::test_open_episode_below_k_is_unresolved` | An episode still open at the end of data without reaching *k* is open, not below *k* |
| `::test_trailing_window_scales_daily_baseline` | A 12-hour window compares with half the daily baseline; the unscaled rule produced no onset |
| `::test_grid_pass_matches_single_cell_detection` | One pass for 36 cells equals 36 single-cell runs on a seeded series |
| `tests/backtest/test_cli.py::test_count_cli_refuses_oversized_or_unrepresentable_series_before_expanding` | Oversized series are refused before any row is built; unrepresentable times are refused, not raised |
| `::test_series_segment_count_is_bounded` | Topics cannot carry more than the registered maximum of segments |
| `::test_count_cli_renders_stamped_report` (extended) | The `k_floor` column shows binds over eligible with a share |

The episode detector now reads through `VisibilityCursor`, so the strict
visibility rule has one definition outside SQL and an equivalence test against
the reader. Measured: all new or changed tests failed before their fixes; five
deliberate mutations (a strict `<` in the cursor, an invented crossing, an
unscaled trailing window, open episodes as below *k*, and no size check before
expansion) each fail at least one test. The single-pass detector produced the same
counts in all 36 rows of the example report as before, and one example run fell
from 0.68 to 0.20 seconds (single run each). 452 Python tests and 14 Node tests
passed; 95% combined coverage; Ruff passed.

## Registered origin and test-fold counting, 2026-10-02

The registration now fixes the §A.5 walk-forward constants: history start *D*0
at a local midnight, a 28-day burn-in covering the baseline window, a 90-day
training span and 7-day folds. The first origin *O*1 = *D*0 + 118 days is derived.
Counting refuses a series that does not start at *D*0, assigns each eligible
episode to the span and fold of its τ_k, applies *K*min and the week floor to the
test span only, and reports the pre-origin span separately as never a test fold.
The example series now covers the pre-origin span and eight weekly test folds.

| Named test | Verified contract |
| --- | --- |
| `tests/backtest/test_registration.py::test_first_origin_is_registered_constant` | *O*1 is *D*0 + 118 days; a changed constant breaks the lock; an unaligned start, a short burn-in and a zero fold are rejected |
| `tests/backtest/test_positives.py::test_positives_counted_only_in_test_folds` | A pre-origin positive stays out of the test span; τ_k exactly at *O*1 and an onset before *O*1 with τ_k after it both count in the test span |
| `::test_week_floor_uses_registered_folds` | Sunday and Monday positives share a fold that a calendar week would split; a pre-origin episode cannot be summarised as a test fold |
| `::test_count_refuses_series_not_starting_at_history_start` | A series starting a day late writes no report |

Measured: the new tests failed before the change; five deliberate mutations (an
exclusive origin boundary in either direction, calendar weeks, no start check and
partition by onset) each fail at least one test. The example report's primary cell
has 3 positives and 3 negatives in the test span across 3 folds, and 2 positives
and 4 negatives before *O*1: far below *K*min, so "not backtestable", a fixture
property and not a feasibility finding. The measured addendum is still supplied;
computing it by registered rules is the next step.

## Measured addendum computed by registered rules, 2026-10-02

The measured addendum is no longer supplied. `sentira/backtest/measurement.py`
computes it from rows published in [*D*0, *O*1) and visible at *O*1: `c_min` and
`k_floor` from the median and MAD of the pooled pre-origin hourly volumes, then
episodes under those thresholds, then the median excess half-life and hence *H*.
The addendum records the pre-origin digest and its intermediate statistics.
`measure` refuses a series that does not reach *O*1 and never replaces an
addendum; `lock` never replaces a lock; `count` recomputes the addendum from the
counted series and refuses any difference. Hand-computed tests now use
`tests/fixtures/hand-measured.toml`, kept separate from the computed example.

| Named test in `tests/backtest/test_measurement.py` | Verified contract |
| --- | --- |
| `test_c_min_and_k_floor_follow_registered_rule` | Median 2, MAD 1 give `c_min` 70 and `k_floor` 15 (hand-computed); an empty series falls back to the registered minimums |
| `test_half_life_recovered_on_synthetic_decay` | Decays with half-lives of 6 h and 20 h are recovered within one hour and map to *H* = 24 and 72 h |
| `test_half_life_counts_from_last_peak_to_half_inclusive` | The last peak and an inclusive half threshold are used; a flat episode has no half-life |
| `test_horizon_is_smallest_registered_value_covering_the_multiple` | 8 h maps to 24 h and 9 h to 72 h; too few half-lives give 168 h |
| `test_addendum_invariant_to_rows_after_first_origin` | Rows published at or after *O*1, or visible only after it, leave the addendum unchanged |
| `test_addendum_refused_until_preorigin_span_complete` | A series ending one hour before *O*1, or starting after *D*0, is refused |
| `test_count_refuses_when_preorigin_data_differs_from_measurement` | An added pre-origin segment, or a hand-edited and relocked `c_min`, is refused |
| `test_shipped_measured_addendum_reproduces` | The shipped addendum equals the computation and its rendering byte for byte |
| `test_measure_lock_count_workflow` | `measure`, `lock` and `count` succeed in order; repeated measure and lock refuse to overwrite |

The rules are a proposal for synthetic development: §A.3 names the inputs but not
the formulae, so confirmatory rules need operator approval before v1. λ and the
MDE are not computed. For the example series the addendum is median 1, MAD 1,
`c_min` 46, `k_floor` 15, four half-lives with a median of 1 hour (its bursts are
step functions) and *H* = 24 hours (calculated by the registered rules from
synthetic data). The example report then has 2 positives and 2 negatives in the
test span of the primary cell.

Measured: the measurement tests failed at collection before the module existed;
seven deliberate mutations (no recomputation in `count`, an unscaled MAD, the first
instead of the last peak, a strict half threshold, a strict horizon threshold,
admitting rows published at *O*1 and no completeness check) each fail at least one
test. Two `count` runs on the example produced identical bytes.

## Second review: half-life window, certifying locks and consistency, 2026-10-02

A high-effort review of `14e76a7..c0f59b3` produced ten findings; two were
reproduced by the reviewer. Fixed:

| Named test | Verified contract |
| --- | --- |
| `tests/backtest/test_measurement.py::test_half_life_includes_the_hour_that_opened_the_episode` | A spike in the hour before onset is the peak; previously no half-life was found, so fast decays were dropped and *H* was biased upwards |
| `::test_half_life_recovered_on_synthetic_decay` (tightened) | Half-lives of 6 h and 20 h are now recovered exactly, not within one hour |
| `::test_lock_refuses_addendum_that_does_not_reproduce` | `lock` refuses the hand-chosen fixture and an incomplete pre-origin span; a lock now certifies a reproducible addendum (§A.9) |
| `tests/backtest/test_registration.py::test_measured_half_life_and_horizon_must_be_consistent` | A half-life without enough episodes, a horizon that does not follow from it, a zero half-life and a missing half-life are rejected |
| `::test_unrepresentable_history_start_is_rejected_not_raised` | An unrepresentable history start is a validation error, not an uncaught overflow |
| `tests/storage/test_asof.py::test_cursor_and_reader_agree_on_visibility` (extended) | Storage refuses a row updated after its observation, which is why the reader's extra `updated_at <= T` clause is implied |

Also: the cursor computes its sort keys once; a duplicated start check and a
duplicated hour constant were removed. With the corrected window the example
addendum records five half-lives instead of the four reported in the previous
section; that earlier figure came from the biased rule and is superseded. The
median stays 1 hour and *H* 24 hours, and the example report is unchanged: 2
positives and 2 negatives in the primary cell's test span.

Not changed, with reasons: the quiet end rule at a zero baseline follows the
registered definition and is recorded as an open question in the specification;
replaying the pre-origin span once for measurement and once for counting is kept
because both reads go through the one visibility rule, at a measured cost below a
second for the example. Measured: the new tests failed before their fixes; five
deliberate mutations (half-life from onset, a lock without recomputation, no
half-life consistency, no horizon consistency, an unconverted overflow) each fail
at least one test. 473 Python tests passed.

## Operator decisions on measurement rules and sparse topics, 2026-10-02

The operator was asked, in plain terms, about the two open methodological points.
Decisions:

| Question | Decision |
| --- | --- |
| Measurement rules for `c_min`, `k_floor` and *H* | Provisionally approved for synthetic development; to be confirmed or revised against pilot data before v1 is locked |
| Quiet end rule at a zero baseline | Changed: with a zero baseline, a zero trailing count is quiet. Other baselines keep the strict rule |

Named test: `tests/series/test_episodes.py::test_zero_baseline_episode_ends_after_a_silent_day`.
An episode whose last rows are at 11:30 now ends quietly 59 hours after the start
of that day instead of at the maximum duration; the closing of a below-*k* episode
in `test_open_episode_below_k_is_unresolved` moved from the maximum duration to a
quiet end at 50 hours accordingly. Both expectations failed before the change. No
other label or count changed, and the shipped measured addendum still reproduces
byte for byte. Measured: 474 Python tests passed.

## Quota ledger and metered client, 2026-10-02

Second step of the plan approved on 2 October 2026. The binding rules "no endpoint
outside the registered set" and "the quota ledger is debited before each call" now
have code and named tests, with synthetic transports only. `config/quota.py`
validates the policy, `storage/quota.py` keeps the persistent ledger (the database
driver stays in storage) and `collectors/quota.py` provides the metered client and
`drain`. The example policy `examples/synthetic-quota.toml` carries the calculated
reservations of BACKTEST §B: 6,000 live, 3,000 retrieval, 500 survival and 500
buffer units, with only live collection allowed into the buffer. No API client,
credential or collection is added. Design and deviations:
[quota-ledger design](superpowers/specs/2026-10-02-quota-ledger.md).

| Named test | Verified contract |
| --- | --- |
| `collectors/test_quota.py::test_shipped_policy_matches_the_calculated_reservations` | The example policy validates with the calculated reservations; `search.list` has no cost |
| `::test_policy_reservations_must_sum_to_daily_units` | Eleven invalid policies are refused, including a negative reservation whose total still matches and a registered write method |
| `::test_ledger_debited_before_call` | The transport sees a pending debit for its own endpoint on every call |
| `::test_ledger_units_equal_calls_made` | Over 200 seeded random calls: 85 debits, 85 transport calls, equal units, 115 refusals, 3 failures |
| `::test_exhaustion_stops_cleanly_and_persists_collected` | With 5 retrieval units, `drain` stops after 5 of 10 requests and the sink holds the 5 results in order; a live run is then served in full, and all 8 debits persist across reopening |
| `::test_drain_reports_completion_when_quota_suffices` | All requests served gives no stop reason |
| `::test_retrieval_cannot_spend_live_reservation` | Retrieval and survival stop at their reservations; live then spends its own and the buffer only |
| `::test_unregistered_endpoint_refused_before_any_debit` | `search.list`, an unregistered list method, a write method and an unknown purpose leave no debit and no call |
| `::test_quota_day_resets_at_registered_offset` | At an offset of −480 minutes the quota day turns over at 08:00 UTC, not at 07:59:59 |
| `::test_debits_survive_reopen_and_refuse_clock_regression` | Outcomes persist; settling twice and a clock one second earlier are refused |
| `::test_policy_change_keeps_the_days_spend` | After 2 retrieval units under a 3-unit policy, a 2-unit policy refuses the next retrieval debit the same day; each debit records its policy digest; a new offset and a regressed clock at adoption are refused |
| `::test_unrecorded_outcome_leaves_debit_pending_and_spent` | A clock stepped back during the call leaves both debits pending and spent; the result and the transport error reach the caller unchanged |
| `::test_failed_call_still_spends_units` | A failing transport leaves a failed debit that still counts towards the day |
| `storage/test_quota_ledger.py::test_two_handles_cannot_overspend_a_reservation` | Two handles on one file share 3 units; the fourth debit is refused |
| `::test_pending_debit_counts_as_spent_after_reopen` | A debit left pending by a stopped process still counts |
| `::test_ledger_refuses_a_foreign_database` | The ledger and document storage refuse each other's files |
| `::test_settle_and_inputs_are_validated` | Unknown debit ids, non-boolean outcomes, the buffer as a purpose, a closed ledger, an invalid policy and a naive clock are refused |

Measured: the first 18 quota tests failed before the modules existed; the other
9 were added after the implementation and the review below. Seventeen deliberate
mutations each fail at least one test: debiting after the call, no
reservation check, the buffer open to every purpose, cost 1 for unregistered
endpoints, a quota day that ignores the offset, failed debits excluded from the
spend, no clock check, no policy check, no reservation-sum check, negative
reservations allowed, write methods registrable, `drain` not catching exhaustion
a per-handle spend cache, settle errors propagating, a new policy refused, an
offset change accepted, adoption without the clock check and the day's spend reset
on adoption. The two-handle test runs in one process; parallel processes rely on
SQLite immediate transactions and are not tested.

A high-effort review of the first commit raised ten points. Fixed: a failed
settle could replace the transport's result or error; one queue of mixed purposes
let exhausted retrieval stop live requests, so `drain` now serves one purpose per
run; a policy change forced a new ledger file that forgot the day's spend, so a
policy with the same offset is now adopted within the ledger and recorded per
debit; the spec now registers the later reset where the provider follows daylight
saving; this entry overstated result persistence and the red-test count; the
example cited the superseded feasibility profile; and the guarantee table now
names the implemented search refusal. Not changed: rebuilding two small
dictionaries per debit, which is negligible beside a network call. The shared
storage scaffolding across three ledgers is left for a separate refactor.
After the fixes, 501 Python tests passed with 96% line and branch coverage; ruff
check and format and the 14 Node tests passed.

## Polling schedule and replay visibility, 2026-10-02

First part of the pilot preparation in the plan approved on 2 October 2026.
`config/collection.py` validates the collection policy *P* and
`collectors/policy.py` computes discovery ticks, the poll jobs of one video and
replay times. The example policy carries the proposed values of BACKTEST §0.3;
none is measured. No API client or collection is added. Design, assumptions and
deviations: [collection-policy design](superpowers/specs/2026-10-02-collection-policy.md).

| Named test in `tests/collectors/test_policy.py` | Verified contract |
| --- | --- |
| `test_shipped_policy_validates`, `test_invalid_policies_are_refused` | The example validates; ten malformed policies are refused, including an interval that does not divide a day and non-increasing ages |
| `test_discovery_follows_registered_ticks` | 02:30 is discovered at 06:00, a tick at itself, 23:59 at the next midnight |
| `test_no_poll_before_discovery` | Discovery 3.5 h after publication polls the 1 h age at discovery and records it as missed |
| `test_late_discovery_coalesces_missed_ages` | Discovery at 30 h gives one job for 1, 6 and 24 h, then single jobs for 72 h, 7 d and 30 d |
| `test_future_ages_anchored_to_publication` | Later jobs fall at publication plus age, late or on time |
| `test_restart_preserves_completed_jobs` | After age 1 h completes and a restart at 30 h, one job covers 6 and 24 h; age 1 h never returns |
| `test_catch_up_after_last_age_is_live_only` | Discovery at 800 h gives one live-only job; discovery exactly at 720 h covers every age on time; replay uses the nominal schedule |
| `test_row_beyond_page_cap_never_replay_visible` | With four threads per poll, the two oldest of six burst threads never become visible |
| `test_row_after_last_poll_age_never_replay_visible` | A thread one minute after the 30-day poll is never visible; one at that instant is |
| `test_tied_rows_at_page_cap_are_not_admitted` | A tie across the cap admits none of the tied threads |
| `test_replay_inputs_are_validated` | A thread before its video, a negative latency, a naive time and an unvalidated policy are refused |
| `test_replay_matches_live_visibility_on_synthetic_complete_history` | On five seeded videos of 200 threads, replay equals an independently written collector paging a synthetic provider |

Measured: the tests failed at collection before the modules existed. Twelve
deliberate mutations each fail at least one test: polling before discovery, no
coalescing, later ages anchored to discovery, completed ages ignored, restart
ignored, the catch-up not flagged, the page cap ignored, no stop at the last-seen
thread, ties admitted, latency dropped, discovery one tick late and a strict due
boundary that silently dropped an age due exactly at discovery. An interrupted
mutation run once left the latency mutation in the working tree; it was found by
the failing tests and restored before commit.
A high-effort review of the commit raised nine points. Fixed: with discovery
slower than the last age, the nominal schedule counted a live-only catch-up as a
replay poll, admitting threads posted after the last age; the shipped policy could
not reveal it, so `test_catch_up_never_counts_as_a_replay_poll` uses a 12-hour
discovery and ages of 1 and 6 hours. Both policies are now validated at
construction, not only when loaded. Completed ages must be integers that were due
by the restart. Unrepresentable times raise `ValueError`. Replay bisects sorted
times instead of scanning every thread per poll. The bounded-integer validator,
copied four times, now lives in `core/registration.py`. Test helpers check that
their text replacements matched, and BACKTEST names the implemented replay test.
Not changed: the one-line `HOUR` constant stays local rather than coupling
collectors to the series package. Eighteen mutations of the revised code, the
three new rules included, each fail at least one test.
530 Python tests passed with 96% line and branch coverage; ruff check and format
and the 14 Node tests passed.

## Quota cost projection, 2026-10-02

Second part of the pilot preparation. `config/volume.py` validates fictional
volume assumptions and `collectors/cost.py` projects the daily units of policy *P*
on its own schedule; the `cost` command writes the report. Design:
[cost-projection design](superpowers/specs/2026-10-02-cost-projection.md).

| Named test in `tests/collectors/test_cost.py` | Verified contract |
| --- | --- |
| `test_shipped_projection_matches_documented_arithmetic` | 240 discovery and 3,600 poll units, 3,840 against 6,000; 661,380 units and 221 days per history-year (BACKTEST §B: about 220, from 220.46 rounded down) |
| `test_projection_uses_the_registered_schedule` | With 12-hour discovery and ages of 1 and 6 hours, coalescing gives 1.5 polls per video and 900 poll units |
| `test_every_call_costs_a_page_even_when_nothing_is_new` | Four polls with no new threads still cost a unit each; a channel with no new videos still costs a discovery page per tick |
| `test_page_cap_bounds_poll_cost_and_reports_lost_threads` | 2,500 new threads at the first poll cost 10 pages and lose 1,500 threads per video; 500 at a later poll cost 6 pages |
| `test_later_polls_read_one_page_past_their_new_threads` | 100 new threads cost one page at the first poll and two at a later one |
| `test_heavy_tail_is_costed_by_stratum_not_by_mean` | With 5% of videos at 5,000 threads, polls average 7.7 pages per video and lose 37,500 threads a day |
| `test_threads_after_the_last_poll_age_are_reported` | A last share of 0.8 leaves 36,000 threads a day never observed live |
| `test_playlist_ceiling_warns_when_a_history_year_is_unreachable` | At 60 videos per channel-day, 333 days are reachable and the report warns |
| `test_ceiling_division_is_exact_for_large_values` | Day counts use exact integer ceiling division |
| `test_live_overrun_is_reported_not_hidden` | 200 channels need 12,800 live units; the report states an overrun of 6,800 |
| `test_missing_retrieval_reservation_is_reported` | A zero retrieval reservation is stated, not divided by |
| `test_invalid_volume_assumptions_are_refused`, `test_shares_must_match_poll_ages` | Twelve invalid assumption files and a share list of the wrong length are refused |
| `test_report_labels_every_figure_calculated` | The report is byte-identical across runs, labels figures calculated, marks four rows assumed and carries the three input digests |
| `test_cost_command_writes_report_and_refuses_overwrite` | The command writes once, refuses to replace without `--overwrite` and refuses a non-Markdown output |

Measured: the tests failed at collection before the modules existed. Twelve
deliberate mutations each fail at least one test: a miscounted discovery tick, the
page cap ignored, no minimum page per poll or per discovery call, shares read as per-interval instead of
cumulative, the schedule bypassed, retrieval days rounded down, an overrun hidden,
lost threads ignored, retrieval playlist pages dropped, share length unchecked and
decreasing shares accepted. The minimum-page mutation first survived; the
nothing-new test was added for it.

A high-effort review of the first commit raised nine points. Fixed: costing on
the mean thread count understated pages and lost threads for a heavy tail, so
threads are now strata; a later poll was charged one page short of the page that
holds its stop thread; threads after the last poll age were neither costed nor
reported; retrieval days used float division; the playlist item ceiling of
BACKTEST §D.6 was ignored; the 221-day figure was presented as identical to
BACKTEST's "about 220"; the README map omitted the new modules; and the report
carried digests copied beside the objects they came from. Not changed: the
projection still iterates every publication minute of a discovery interval
(1,440 schedules at most, milliseconds), because a closed form would duplicate
the scheduler's coalescing rule; and the share-length check stays explicit for
its message. Fifteen mutations of the revised code each fail at least one test.
556 Python tests passed with 96% line and branch coverage; ruff check and format
and the 14 Node tests passed.

## Locked pilot registration, 2026-10-02

Third part of the pilot preparation. `backtest/pilot.py` validates the pilot
registration of BACKTEST §A.9 and writes or verifies its lock; `lock-pilot` is the
command. The lock binds the pilot to the collection policy, quota policy and
volume assumptions by digest, records the lock time and the projected pilot cost,
and is refused after collection starts or above the quota ceiling. Excluding pilot
data from confirmatory test folds is deferred to the v1 step. Design:
[pilot-registration design](superpowers/specs/2026-10-02-pilot-registration.md).

| Named test in `tests/backtest/test_pilot.py` | Verified contract |
| --- | --- |
| `test_shipped_pilot_validates_and_lock_verifies` | 12 channels; projected 768 × 14 + 10,148 = 20,900 units within 30,000; the lock reproduces byte for byte |
| `test_selection_schema_has_no_place_for_a_counter` | A subscriber floor in a stratum, a view floor in the selection and a trending flag are refused as unknown fields |
| `test_invalid_pilots_are_refused` | Registration after collection start, 91 history days, an empty stratum, 61 channels, a duplicate stratum, a hand-picked selection, a zero ceiling and live mode are refused |
| `test_unknown_adaptation_refused` | An adaptation outside the registered set is refused |
| `test_live_days_cover_latency_measurement` | Seven live days are accepted, six refused |
| `test_pilot_lock_refused_after_collection_start` | A lock at collection start is accepted, one second later refused |
| `test_pilot_lock_refuses_projected_cost_above_ceiling` | A ceiling of 20,900 is accepted, 20,899 refused |
| `test_changed_policy_quota_or_volume_refused_after_lock` | Changing any of the four input files after locking is refused |
| `test_tampered_lock_record_refused` | An edited projection, a later lock time, another schema, an extra field or a malformed time is refused |
| `test_pilot_lock_never_overwritten` | A second lock is refused by exclusive creation |
| `test_lock_pilot_command` | The command reproduces the example lock, refuses to replace it, refuses a late lock and refuses an input as output |

Measured: the tests failed at collection before the module existed. Ten
deliberate mutations each fail at least one test: a late lock accepted, the cost
check dropped, the digest check skipped, an unknown adaptation accepted, a short
live run accepted, registration after collection start accepted, the sample size
unbounded, the history span left out of the cost, the full channel list costed
instead of the sample, and an unchecked projected cost. The last first survived;
the tampered-lock test was added for it. 583 Python tests passed with 96% line and
branch coverage; ruff check and format and the 14 Node tests passed.
