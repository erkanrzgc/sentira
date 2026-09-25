# Offline procedural case register

Status: approved by the operator on 25 September 2026. No runtime behaviour is
added by this document. The operator has authorised work on case recording and
stage tracking; this document bounds the first implementation.

## Purpose and approach

Turn explicitly synthetic, operator-authored procedural evidence into a
deterministic case report. A report answers what is documented, where the evidence
is, when it was observed, and which questions remain unresolved. It does not
predict legal outcomes, prices or construction.

Three approaches were considered:

| Approach | Trade-off |
|---|---|
| Separate offline case register, recommended | Small explicit contract; preserves existing briefing domains and tests |
| Extend the three-domain scenario ledger directly | Reuses persistence but couples procedural events to scenario eligibility |
| Start with model extraction | Introduces semantic errors before a reference contract and evaluation exist |

The first approach uses existing UTC validation and safe report writing, with
focused case modules. No generic workflow framework is required.

## Inputs and separation

External TOML files contain source definitions, fictional cases, reviewed event
records and reporting labels. No institution names, source addresses or case
facts are hard-coded. Source addresses use HTTPS and are rendered as links only;
the application never fetches them. Fixtures use reserved example domains.

The loader requires `synthetic = true`, rejects unknown fields and validates
references before rendering. This declaration is a fixture contract, not a
semantic detector of real data. Real research remains outside the repository;
real-data ingestion requires a later source-use and lifecycle amendment.

Each case has an explicit stable ID and a short institutional matter description.
The register contains no owner, author, account, person-target or signature field.
Free text is operator supplied; schema restrictions do not prove text contains
no personal information. Location descriptions distinguish an affected area
from an adjacent reference. Dates or matching topics never merge cases.

Each event contains an ID, case ID, registered institution/source ID, decision
reference where applicable, event kind, event date, exact UTC observation time,
source URL, positive one-based page number, original short summary, and review
method (`text` or `visual`). Source publication date is optional and distinct
from event date and observation time. No midnight timestamp is invented from a
date-only observation; such input is rejected by this first synthetic slice.

Event kinds are fixed by schema: `proposal`, `referral`, `acceptance`,
`display_notice`, `display_closure`, `objection`, `objection_outcome`,
`amendment`, `cancellation`. An acceptance identifies its issuing institution;
there is no universal highest approval level. Display notices may carry an
explicit start date and positive stated duration in days. The duration never
creates a closure event.

## View and report

One pure view function is the only selector used by the renderer. It accepts the
validated snapshot and a UTC cutoff. Only events observed by the cutoff are
visible; future-dated notices may be visible but their stated event dates remain
explicit. Issuance cannot precede the cutoff. An old event date never backdates
availability. The snapshot is supplied anew for each run: durable first-observed
enforcement, immutable issuance and historical reconstruction are not claimed.

Reports list visible evidence in stable order and present separate dimensions:
documented acceptances, display notice, closure evidence, objections/outcomes,
and amendments/cancellations. They do not collapse these into a numeric progress
bar or a definitive current legal status. Absence means 'no evidence in this
snapshot', never 'no objection occurred'. Multiple inconsistent records are
shown for review without silently selecting a winner.

An event may explicitly supersede an earlier event in the same case. Reject
missing targets, cross-case targets and cycles. Once a superseding event becomes
visible, mark the earlier record as superseded and the case as requiring review;
do not automatically apply the replacement as a new legal status. Earlier
cutoffs retain the earlier view. Unavailable or omitted documents cannot be
detected from a supplied snapshot and are stated as a limitation.

Every summary links to its source and page locator. Markdown/HTML content is
escaped. Repeated documents from one source remain one origin; no corroboration
score is calculated. Report headers say 'synthetic procedural evidence report'.

## Components and command

Planned modules: `core/cases.py` for immutable records and validation,
`config/cases.py` for TOML loading, `report/cases.py` for the pure cutoff view and
renderer. No database or network dependency is added. Reuse `write_report` and
UTC parsing without changing the existing `briefing` command.

Proposed command: `case-report --input FILE --cutoff UTC --issued-at UTC
--output FILE`, with explicit `--overwrite`. Output must be a separate Markdown
path. Validate the entire input and render successfully before opening output;
invalid input leaves existing output untouched.

## Acceptance checks

The implementation plan must provide named tests for these contracts:

| Test | Required result |
|---|---|
| `test_same_date_and_topic_do_not_merge_cases` | Explicit case IDs retain separate events |
| `test_adjacent_location_is_not_affected_parcel` | Location relation survives rendering |
| `test_event_date_does_not_backdate_observation` | Later-observed records stay out of earlier views |
| `test_invisible_events_do_not_change_report` | Future observations leave earlier report bytes unchanged |
| `test_duration_does_not_create_closure` | Elapsed notice duration cannot establish closure |
| `test_missing_outcome_is_unknown` | Missing evidence does not become a negative finding |
| `test_supersession_requires_review_at_cutoff` | Revision flags appear only when observed |
| `test_invalid_supersession_rejected` | Dangling, cross-case and cyclic references fail |
| `test_case_input_contract_is_strict` | Unknown fields, invalid pages/times and real-data declarations fail |
| `test_case_report_escapes_source_text` | Input text cannot become active markup |
| `test_invalid_case_input_preserves_output` | Failed validation cannot damage prior output |
| `test_case_report_is_deterministic` | Identical inputs and timestamps produce identical bytes |

Use original synthetic fixtures only. Run focused new tests, existing full tests
and Ruff once implementation is ready. Software checks do not measure semantic
accuracy or forecasting value. Model selection requires a separate human-reviewed
evaluation, simple-rule and majority/random baselines, and checks of uncertainty
and source attribution. No model is downloaded or trained in this increment.
