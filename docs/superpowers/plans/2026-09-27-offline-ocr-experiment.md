# Offline OCR experiment implementation plan

> **For agentic workers:** Use subagent-driven development for the isolated
> scoring module and review; execute fixture preparation and comparison in order.

**Goal:** Measure exact field recovery on four original fictional document pairs.

**Architecture:** Keep the research command in `experiments/ocr/`, separate from
the installed package and production CLI. Standard-library scoring has offline
unit tests. An optional PDF runner uses locally available PDF libraries and an
explicit local OCR executable. TOML supplies all document content and rules.

**Tech stack:** Python 3.12, TOML, hashlib, subprocess, reportlab, pypdf, Poppler,
Tesseract. No network access in the runner or tests; dependency retrieval is a
separate provenance-recorded preparation action.

## Tasks

- [x] Add `experiments/ocr/scoring.py` and `tests/experiments/test_ocr_scoring.py`.
  First demonstrate failing tests for changed digits/units, missing and repeated
  fields, paired baseline determinism and modified registration rejection. Then
  implement `extract_fields(text, labels)`, `score_fields(expected, extracted)`,
  `baseline_predictions(families, field_names, seed)` and
  `verify_lock(directory)`. Tests use only original strings and temporary files.
- [x] Add `experiments/ocr/fixtures.toml` with four fictional families, field
  labels, durations, references, dates, scales and fixed rendering/OCR settings.
- [x] Add `experiments/ocr/run.py`: `prepare` authors paired PDFs, rasterises each
  using explicit Poppler, checks image-only pages have no extractable text, and
  records versions/digests. `lock` records explicit visual-review acknowledgement.
  `compare` verifies the lock and every registered digest before subprocesses,
  runs extraction and OCR, retains raw text/errors, and emits JSON and Markdown.
  Output directories must be new, input/config files must never be overwritten.
- [x] Record official recognition-data provenance, licence and SHA-256; store
  downloaded data only in ignored experiment output. Render and inspect all eight
  pages before locking. Run the fixed comparison once and preserve all failures.
- [x] Run focused offline tests, full suite and Ruff. Request independent static
  review, fix evidenced defects, then document measured results and their limits.
  Integrate locally only; no push or release.

## Verification commands

```powershell
python -m pytest tests/experiments -q
python -m pytest --cov=sentira --cov-branch --cov-fail-under=80
python -m ruff check .
python -m ruff format --check .
```

The OCR executable is exercised only by the explicitly invoked local experiment,
not the normal test suite. Missing recognition data is an unrun state, not a
measured accuracy. Registration mismatches must fail before engine invocation.
