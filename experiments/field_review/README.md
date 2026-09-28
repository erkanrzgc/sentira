# Explicit synthetic field review

The OCR development stress run produced plausible wrong values. This separate
workflow keeps recognition candidates pending until a field receives an explicit
decision. It uses only original synthetic experiment outputs and the standard
library; it does not call an OCR engine or modify the case ledger.

```powershell
python -m experiments.field_review.run packet `
  --fixtures out/ocr-stress-v1 --results out/ocr-stress-results-v1/results.json `
  --output out/field-review-packet
```

The packet identifies each candidate by page and field, links its registered
image and digest, and omits authoring answers and baseline predictions. The
generated `decisions.toml` contains no preselected acceptance. Inspect the source
image before recording a decision. Repeated development pages are not independent
human reference data just because authoring answers are omitted here.

To record decisions, retain the generated packet digest and replace `reviews = []`
with tables such as these **simulated examples**, using identifiers from the packet:

```toml
[[reviews]]
field_id = "fixture-a-image:date"
action = "correct"
value = "2030-02-08"
reason = "Simulated review: transcription checked against the fictional page."

[[reviews]]
field_id = "fixture-a-image:duration"
action = "accept"

[[reviews]]
field_id = "fixture-a-image:scale"
action = "withhold"
reason = "Simulated review: interpretation intentionally left unresolved."
```

Run the report into a new directory:

```powershell
python -m experiments.field_review.run report `
  --fixtures out/ocr-stress-v1 --results out/ocr-stress-results-v1/results.json `
  --decisions out/field-review-packet/decisions.toml --output out/field-review-report
```

Every omitted field remains pending. Only explicitly accepted or corrected values
appear as usable fields. Missing, ambiguous or failed recognition cannot be
accepted; an explicit correction is required. A correction is an operator-supplied
value, never an automatic lookup of the authoring answer. Withholding carries a
reason and no value. All fields remain visible as reviewed entries or gaps.

Source, registration or results changes invalidate the packet binding. Unknown
and duplicate field decisions fail. Output directories must be new, so a report
never silently replaces an earlier review. TOML edits are external configuration;
no reviewer identity or authentication is supplied by this development command.

Explicit review does not prove that a decision is true. This module implements
neither an independent evaluation nor a calibrated abstention policy. Source-use,
lifecycle, representative evaluation and product-integration requirements remain
unresolved. Do not ingest real documents or use the report as a legal conclusion.
