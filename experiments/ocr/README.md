# Local synthetic OCR experiment

This development experiment is separate from the installed Sentira package.
It compares ordinary PDF extraction with local OCR on four original fictional
document families, each supplied as a selectable-text and image-only page.
It does not accept an arbitrary document directory or feed a case ledger.
The synthetic declaration is a usage contract, not a semantic privacy detector.

## Preparation

Use Python 3.12 with `reportlab`, `pypdf` and Pillow available, plus explicit local
paths to Tesseract, Poppler's `pdftoppm`, a permitted font and recognition data.
The normal application and test suite do not require these optional libraries.
Record recognition-data provenance and licence separately before preparation.
No command here downloads dependencies or contacts a service.

```powershell
python -m experiments.ocr.run prepare `
  --config experiments/ocr/fixtures.toml `
  --font <local-font-file> --poppler <pdftoppm-executable> `
  --engine <tesseract-executable> --data <recognition-data-directory> `
  --language <recognition-code> --output out/ocr-fixtures
```

Inspect all eight generated PNG pages against the TOML values. The authoring
command refuses image-only PDFs containing extractable text. Then explicitly
acknowledge visual inspection and run the registered comparison:

```powershell
python -m experiments.ocr.run lock --directory out/ocr-fixtures --reviewed-all-pages
python -m experiments.ocr.run compare --directory out/ocr-fixtures --output out/ocr-results
```

Every output directory must be new. A changed registration, input file, executable,
recognition file or recorded library version requires a new preparation and
review; do not edit a lock to make it pass. The lock detects accidental drift,
not deliberate replacement of both registration and lock. Native library
dependency files and package contents are not exhaustively fingerprinted.

## Reading results

`results.json` retains all per-field expected/actual values, missing or ambiguous
outcomes, raw output and process times. Native stdout/stderr bytes are preserved
as base64, including undecodable output. A timeout or unreadable native output
does not contribute a successful field. `results.md` shows exact-match counts
alongside majority and seeded random baselines, separately by representation.

The field parser accepts exactly one line beginning with the configured label
and colon. It trims outer whitespace only. A changed digit, separator or duration
unit is a mismatch. This intentionally measures a labelled template; it is not a
general procedural-document parser. Expected values are not used for extraction.

All four families are development data with author-provided answers; paired pages
are not independent samples. The tiny clean-page test does not establish
target-language accuracy, performance on degraded scans, human effort savings,
legal interpretation or forecasting value. Changing a rule after seeing results
creates another development experiment, not a corrected original score.

## Offline tests

```powershell
python -m pytest tests/experiments -q
```

Unit and orchestration tests replace the native subprocess boundary and PDF
extraction boundary; they never run a native engine or access the network. The
explicit experiment command is the separate native integration check.
