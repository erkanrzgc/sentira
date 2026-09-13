# Offline briefing implementation plan

> **For agentic workers:** Execute task by task using `executing-plans` and
> test-driven development. Obtain independent `requesting-code-review` before
> local integration.

**Goal:** Produce a reproducible, clearly synthetic three-domain Markdown briefing
from validated external files, without a network call or language model.

**Architecture:** Immutable TOML configuration and evidence contracts feed a
separate synthetic SQLite evidence ledger under `storage/`. Storage supplies
observation time, enforces append-only identity and registration, and owns the
single evidence read path. The renderer handles only a cutoff-filtered view and
registered scenario drafts; it does not infer events or write new factual claims.

**Stack:** Python 3.12 standard library; existing pinned pytest/coverage/Ruff tools.

## 1. Configuration and evidence contracts

Files: `sentira/config/briefing.py`, `sentira/core/evidence.py`,
`tests/briefing/test_pipeline.py`,
`config/{domains,sources,questions,reporting}.toml`,
`examples/synthetic-evidence.toml`.

- [x] Write contract tests first; run them and verify missing-module failures.
- [x] Implement frozen dataclasses for the three fixed domains, registered sources,
  versioned questions, scenario drafts and reporting settings. Reject unknown
  fields, duplicates, invalid types, naive dates, credential URLs and unresolved
  references. Canonical JSON of validated non-secret configuration gives SHA-256.
- [x] Keep source and question content entirely in TOML. Each source has an
  explicit synthetic HTTPS origin, origin group and synthetic rights record.
- [x] Define synthetic evidence records with attributed claim, domain IDs,
  published time, expiry, support/counterevidence IDs and optional revision ID.
  Input records cannot supply observation time or a claimed digest. Storage
  stamps those values. Corroboration requires a supporting record from another
  registered origin, not merely another URL.
- [x] Run configuration and evidence tests, then preserve a green checkpoint.

## 2. Append-only synthetic evidence ledger

Files: `sentira/storage/evidence.py`, `tests/briefing/test_pipeline.py`.

- [x] Write tests for temporal cutoff, observation-clock ownership, reference
  validation, origin groups, revision validation, atomic rollback and persistence.
- [x] Implement a separate SQLite file with its own schema marker; never change
  the existing document database. Schema creation and writes are transactional.
- [x] Register canonical configuration snapshots and versioned question digests.
  A changed question definition requires a new question ID. Duplicate evidence
  IDs with changed content fail; unchanged re-ingestion preserves first observation.
- [x] Validate every reference inside a batch or existing ledger, reject support/revision cycles
  and prevent cross-domain corroboration. Register configuration and batch in the
  same transaction. Persist monotonic write time even for duplicate batches.
- [x] Build a sorted cutoff view in storage. Exclude observations after cutoff,
  retain evidence references to unavailable/expired records as explicit gaps,
  and never promote a future supporting record into historical corroboration.
- [x] Test failed writes leave no partial evidence or registration state.

## 3. Deterministic briefing and offline command

Files: `sentira/report/briefing.py`, `sentira/cli.py`,
`tests/briefing/test_pipeline.py`, `tests/briefing/test_cli.py`.

- [x] Write tests for all nine acceptance criteria in SCENARIO_DESIGN, including
  same-origin repetition, missing and contradictory evidence, staleness, change
  window, escaping source text and deterministic output.
- [x] Render one shared flow for each domain: question, observed developments,
  registered scenarios with visible support and counterevidence, unknowns,
  strengthen/weaken triggers, review deadline, source coverage and references.
- [x] Suppress unsupported scenarios; never invent a scenario or probability.
  Escape untrusted Markdown/HTML and include source metadata with registered URLs.
- [x] Add `python -m sentira.cli briefing --config config --evidence
  examples/synthetic-evidence.toml --observed-at 2030-01-01T12:00:00Z
  --cutoff 2030-01-01T12:00:00Z --issued-at 2030-01-01T12:00:00Z
  --output out/synthetic-briefing.md`. The CLI uses an ephemeral synthetic ledger;
  its explicit clock is for simulation and cannot be used for a live collector.
- [x] Parse and validate input before writing output; refuse overwriting existing
  output unless explicitly requested. Errors are short and exclude input content.

## 4. Verify, review, document and integrate

- [x] Run the complete suite with branch coverage >=80%, Ruff lint/format, installed
  package command and the example command twice to verify byte-identical output.
- [x] Independent review; reproduce and fix actionable defects with regression tests.
- [x] Update README, SCENARIO_DESIGN, CONTINUATION and the plan with exact measured
  results and limits. Check generic terminology, file links and Git whitespace.
- [ ] Commit locally, fast-forward a still-clean main checkout, verify there and
  remove only the generated worktree. No push, live source, model or forecast.

## Implementation decisions

The first slice stores only synthetic evidence and configuration. Rights records
are synthetic identifiers, not grants of real permissions. Source URLs use the
reserved `.invalid` namespace and are never fetched. Expiry is evaluated at the
briefing cutoff; this is simulated eligibility, not a real deletion service.
Production retention and deletion remain blocked on their separate design.

Question drafts in files are operator-authored, not model-generated. The ledger
locks question definitions by ID; a real forecast ledger and immutable report
issuance history remain later work. File changes produce a different config digest.
The ephemeral example command proves reproducibility for supplied inputs only.

## Execution record

Initial contract and CLI test runs failed at collection because their modules did
not yet exist. After implementation, both passed. The tests use the shared network
blocker and real SQLite transactions. Contract, ledger and rendering tests share
one fixture-driven test module; CLI tests are separate. Mutual contradiction links
are permitted, while support/revision dependency cycles are rejected.

Final worktree verification: 147 tests passed; combined statement/branch coverage
93.21%; Ruff lint and format passed. Editable installation and byte-identical
repeat CLI output were verified. Independent review identified source-registration
leakage in views and incomplete domain coverage in corroboration references.
Both defects were reproduced by failing regression tests, fixed and independently
rechecked (52 briefing tests passed). References now cover every parent domain;
views retain only evidence matching the selected source registration.
