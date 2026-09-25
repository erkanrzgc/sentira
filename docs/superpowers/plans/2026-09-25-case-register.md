# Offline Case Register Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task.

**Goal:** Render synthetic procedural evidence with explicit provenance and gaps.

**Architecture:** Immutable records, strict TOML loading, one cutoff view and a
deterministic Markdown renderer. Reuse existing validation and output helpers;
leave the briefing command and its three domains intact.

**Tech Stack:** Python 3.12 standard library, pytest and Ruff.

## Task 1: Record contracts and external input

Files: `sentira/core/cases.py`, `sentira/config/cases.py`,
`tests/cases/test_cases.py`, `examples/synthetic-cases.toml`.

- [x] Write tests using `load_cases(path)` with a fictional two-case TOML fixture.
  Assert that duplicate IDs, unknown fields, invalid pages, naive observation
  times, unsupported kinds and `synthetic = false` raise `ValueError`.
- [x] Run `python -m pytest tests/cases -q`; confirm missing implementation fails.
- [x] Implement frozen `CaseSource`, `Case`, `CaseEvent`, `CaseSnapshot` records.
  Validate local fields at construction; validate uniqueness, references and
  supersession graphs at snapshot construction. The loader accepts TOML native
  dates and datetimes, with no date-to-timestamp coercion.
- [x] Rerun targeted tests. Keep all concrete evidence and labels in the fixture.

## Task 2: Cutoff view and report

Files: `sentira/report/cases.py`, `tests/cases/test_cases.py`.

- [x] Write tests comparing reports before and after inserting a future
  observation, asserting byte equality at the old cutoff. Check separate case
  headings, adjacent-area wording, missing closure, escaped content, revision
  flags and source/page links. Check issuance before cutoff is rejected.
- [x] Confirm failure, then implement `case_view(snapshot, cutoff)` and
  `render_cases(snapshot, *, cutoff, issued_at)`. Sort cases by ID, events by
  observation time/date/ID; rendering consumes only the selected view.
- [x] Mark visible superseded events and affected cases for review. Display
  each evidence dimension independently without inferring finality or outcomes.
- [x] Run targeted tests until the specified contracts pass.

## Task 3: Command integration and verification

Files: `sentira/cli.py`, `tests/cases/test_cli.py`, `README.md`,
`docs/CONTINUATION.md`.

- [x] Write CLI tests for successful rendering, input/output alias rejection,
  invalid input preserving an existing report, and explicit overwrite behaviour.
- [x] Confirm failure. Add the `case-report` subcommand, validate inputs before
  writing, and retain the existing `briefing` path and failure behaviour.
- [x] Run all tests and Ruff. Run the example command twice to separate files;
  compare bytes and inspect one report.
- [x] Review the diff and record exact measured checks and unimplemented limits.
  Commit locally after checks. Do not push or release.

## Review and limits

The first cut deliberately has no database, collection, OCR, model or live-data
mode. A source URL is a reference, not an access request. Timestamp precision
must be explicit. Neither a display duration nor missing objection records
establishes legal finality. The named tests in the approved spec define the
review checklist; CLI integration must preserve the existing 158-test baseline.
