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
