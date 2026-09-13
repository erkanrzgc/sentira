# Offline foundation implementation plan

> **For agentic workers:** Execute this approved plan task by task using
> `executing-plans`; use `requesting-code-review` before integration.

**Goal:** Establish the approved offline contracts using synthetic data, with no
collector, model, forecast or external report.

**Architecture:** Frozen, validated documents cross a domain-separated HMAC
boundary. SQLite writes stamp the observation clock and commit documents and
snapshots atomically. One strict as-of reader returns only observations available
at the requested instant; no historical replay implementation is included.

**Tech stack:** Python 3.12 standard library at runtime; pytest, pytest-cov and
Ruff for local verification. Development dependencies are pinned after resolution.

## 1. Reconcile the approved contracts

- [x] Update `README.md`, `AGENTS.md`, `docs/CONCEPT.md`, `docs/ROADMAP.md`,
  `docs/BACKTEST.md`, `docs/FEASIBILITY.md` and `docs/FORECASTING.md` to distinguish
  the offline subset from future guarantees.
- [x] Add `docs/SOURCE_USE.md` with retrieved official sources and unresolved
  use-specific decisions. No permission is inferred from an API key.
- [x] Make late discovery, survivor-only replay limits, pilot registration order
  and text lifecycle precedence explicit in BACKTEST.
- [x] Verify Markdown references, generic terminology and `git diff --check`.
- [x] Commit the reconciled design separately from runtime changes.

## 2. Establish validation and identity contracts (red, then green)

Files: `pyproject.toml`, `requirements-dev.txt`, `tests/conftest.py`,
`tests/core/test_document.py`, `tests/core/test_identity.py`,
`tests/config/test_schema.py`; then `sentira/core/document.py`,
`sentira/core/identity.py`, `sentira/config/schema.py` and package initialisers.

- [x] Write tests for immutable documents, exhaustive field classes, aware UTC
  timestamps, hashed identifiers, kind-specific author requirements, synthetic
  provenance and rejection of unknown fields without echoing content.
- [x] Write tests for missing/short keys, HMAC domain separation, deterministic
  results and diagnostics that contain no key or raw identifier.
- [x] Write tests for target kinds PARTY, STATE_INSTITUTION and DECLARED_CANDIDATE;
  reject unknown kinds, keys, empty names and duplicate configured targets.
- [x] Run `.venv/Scripts/python -m pytest tests/core tests/config -q` and record
  missing-contract failures before implementing.
- [x] Implement frozen slotted dataclasses and enums. Use JSON framing of
  `[platform, identifier_kind, raw_id]` for HMAC input, UTF-8 and SHA-256. Load a
  32-byte hex key from `SENTIRA_HMAC_KEY`; errors carry field names only.
- [x] Rerun that command until the contract tests pass.

Representative acceptance contract:

```python
assert hasher.hash("synthetic", IdentifierKind.AUTHOR, "sample") != hasher.hash(
    "synthetic", IdentifierKind.COMMENT, "sample"
)
with pytest.raises(ValueError):
    Document.from_mapping({**valid_fields, "username": "private-value"})
```

## 3. Implement transactional storage and strict reads (red, then green)

Files: `tests/storage/test_repository.py`, `tests/storage/test_schema.py`,
`tests/storage/test_asof.py`, `tests/test_architecture.py`; then
`sentira/storage/schema.py`, `sentira/storage/repository.py`,
`sentira/storage/asof.py` and its package initialiser.

- [x] Write tests against temporary SQLite files and a controllable UTC clock.
  Include re-ingestion, failed writes, reopen, exact-T boundaries, changing future
  rows, offset-equivalent times and counter snapshots observed after T.
- [x] Inspect real SQL columns, constraints and foreign keys; compare field
  classes to dataclass metadata. AST-check that only storage imports sqlite3.
- [x] Run `.venv/Scripts/python -m pytest tests/storage tests/test_architecture.py
  -q` and record failures before implementing.
- [x] Implement `Repository(path, clock=...)` as a context manager;
  `ingest(document, snapshots=())` stamps the injected clock once, validates
  chronology and writes with one transaction. Duplicate documents preserve their
  first observation and content. Reject a regressing write clock.
- [x] Implement `AsOfReader(repository).read(at)` returning frozen visible
  documents and the latest snapshot per document/metric at or before `at`.
  Observation and update timestamps are never feature fields. No database driver
  is imported outside storage. Read results expose no author-query API.
- [x] Ensure malformed input, unsupported provenance, invalid counters and
  timestamp errors cannot leak content; SQL rollback preserves prior state.
- [x] Rerun the storage checks, then all tests.

Representative acceptance contract:

```python
before = AsOfReader(repository).read(at)
clock.advance(hours=1)
repository.ingest(later_document)
assert AsOfReader(repository).read(at) == before
```

## 4. Verify, review and hand off

- [x] Add `tests/test_offline_e2e.py` for synthetic input -> HMAC -> document ->
  repository -> strict read, including a future snapshot that must remain hidden.
- [x] Block socket connection and DNS operations in the test session. Add a test
  demonstrating that the guard rejects a network attempt without sending traffic.
- [x] Run `.venv/Scripts/python -m pytest --cov=sentira --cov-branch
  --cov-report=term-missing --cov-fail-under=80` and
  `.venv/Scripts/python -m ruff check .` plus `ruff format --check .`.
- [x] Install the package locally and run the documented offline smoke example.
- [x] Obtain independent code review, address actionable findings with regression
  tests, and repeat affected checks.
- [x] Record exact commands, results, implemented guarantees and live-data
  blockers in `docs/CONTINUATION.md`; update the README's local instructions.
- [x] Commit locally and integrate the verified change into the project checkout
  if it is still clean and can be fast-forwarded. Do not push or publish.

## Scope audit

Every required check in IMPLEMENTATION_START maps to tasks 2–4. Live scheduling,
registration execution, privacy suppression, refresh/deletion, API quota handling
and replay fidelity are design work only in task 1. They are not marked as
implemented by this increment. Synthetic fixtures are original test data, not
recorded platform responses, and cannot substantiate platform behaviour.

## Execution notes

- Contract suites first failed on missing implementation modules, then passed.
- A parent reference regression failed before its comment-namespace correction.
- Independent review found the duplicate-ingestion clock regression. A failing
  regression preceded the transactional watermark fix; the reviewer confirmed it.
- Final worktree run: 95 tests, 94.99% combined statement/branch coverage, clean
  Ruff lint/format checks and successful isolated installed-package smoke.
- No real-source fixture, credential, internal research or live content was used.
- Fast-forward integration into the local main checkout completed. A fresh local
  virtual environment installed the pinned tools and editable package. The same
  95 tests, 94.99% combined coverage and Ruff checks passed in that checkout.
