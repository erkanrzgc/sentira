# Synthetic source-linked field review

Status: next offline increment under the instruction to continue the reviewed
OCR work. Scope is original synthetic documents only, outside the case ledger.

## Decision

The stress comparison produced plausible wrong dates and identifiers. Automatic
acceptance, heuristic repair and a model-based repair pass would conceal this
failure. Use explicit field review with unchanged source-page linkage instead.
This is a workflow contract, not a guarantee that a reviewer is correct.

## Data flow

1. Load a locked synthetic experiment registration and its recorded results.
   Require every OCR page exactly once and every configured field exactly once.
   Check registration identity and source-page file hashes before proceeding.
2. Create a review packet containing source page identifiers, image digests and
   OCR candidates. Omit authoring answers and baseline predictions. The packet
   is still development material; withholding answers here does not make the
   repeated families independent or blind evaluation data.
3. Bind external TOML decisions to the packet digest. Every field defaults to
   pending. Explicit `accept` retains the recognised candidate; `correct` requires
   a supplied value and reason; `withhold` requires a reason and emits no value.
4. Render a review report. Only accepted or corrected values appear as usable
   fields. Pending and withheld fields appear as gaps. Missing/ambiguous or failed
   OCR cannot be accepted without an explicit correction. All fields remain in
   the report so missing decisions cannot disappear from its denominator.

Changing the source image, registration or results invalidates an earlier review
binding. Duplicate, unknown or malformed decisions fail without replacing output.
No reviewer identity is collected; the experiment records explicit operator
decisions, not an authenticated person or independent human reference.

## Boundaries and tests

Keep this module in `experiments/field_review/` so it does not change the already
locked OCR runner files. It uses only the standard library and never invokes OCR,
downloads data, contacts a service or writes into the case ledger.

Named tests must demonstrate pending-by-default suppression, explicit corrections,
missing/failed candidate rejection, digest mismatch rejection, duplicate and
unknown decision rejection, changed source-page rejection, answer exclusion and
preservation of existing output. Demonstrations use clearly labelled simulated
operator decisions; they do not claim that independent human review occurred.

No confidence score, calibrated abstention threshold, time saving, legal effect
or production readiness is inferred. Real-source rights and lifecycle gates stay
closed. A later product integration requires its own design and validation.
