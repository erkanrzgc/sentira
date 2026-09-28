# Synthetic field review implementation plan

> **For agentic workers:** Use subagent-driven development and independent review.

**Goal:** Prevent unreviewed OCR candidates from appearing as accepted fields.

**Architecture:** A standard-library module derives a packet from locked synthetic
OCR outputs; external TOML records decisions bound to a canonical packet digest.
A small separate CLI writes new review output directories. No product CLI changes.

**Tech stack:** Python 3.12, TOML, JSON, SHA-256 and Markdown.

- [x] Implement `experiments/field_review/core.py` and
  `tests/experiments/test_field_review.py` with test-first packet integrity,
  decision validation and pending-by-default rendering. Reuse read-only
  `experiments.ocr.scoring.verify_lock` for registered synthetic page files.
- [x] Implement `experiments/field_review/run.py` and CLI tests. Commands:
  `packet --fixtures DIR --results FILE --output NEWDIR`; `report` takes the same
  inputs plus `--decisions FILE`. Outputs must be new; configuration stays in
  TOML, inputs never overwritten, no native or network calls.
- [x] Generate a pending packet and a clearly simulated correction/withholding
  example against the recorded stress run. Verify no reference-answer fields
  appear in the packet and no pending values appear in the report.
- [x] Run focused and full tests, Ruff, then independent static review. Record
  limitations and integrate locally without push or release.

Verification: `python -m pytest tests/experiments -q`, then the complete suite
with the existing installed-package coverage gate. Execute the new CLI against
only the already generated synthetic stress artefacts.
