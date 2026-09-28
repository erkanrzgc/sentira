# Offline OCR feasibility experiment

Status: bounded synthetic experiment accepted for implementation following the
operator's instruction to continue after the design summary. Recognition data
may be downloaded to an experiment-local directory with recorded provenance;
no system installation or real-source ingestion is included. Existing runtime
contracts and the deferred analyst-model decision remain unchanged.

## Question and alternatives

Can an available local OCR engine recover procedural fields from original
synthetic image-only pages that ordinary PDF text extraction cannot read?

| Approach | Trade-off |
| --- | --- |
| Local OCR on original synthetic pages | Isolates character recognition from interpretation; recommended first experiment |
| Continue manual visual transcription | Useful reference workflow; recurring human effort is not yet measured |
| Use a general document model | Adds interpretation, model/runtime requirements and uncertainty before extraction is measured |

The source review observed meaningful text on four pages for which the current
PDF extractor returned zero characters. This motivates an extraction experiment;
it establishes neither OCR accuracy nor a recurring human bottleneck.

## Inputs and fixed scope

Use four wholly fictional document families, each rendered twice: selectable-text
PDF and image-only PDF. Eight pages is a calculated workload, not a statistical
sample-size claim. Both representations of each family remain in development;
none is labelled held out or independent human ground truth.

External TOML supplies each family's institution label, decision reference,
calendar date, plan scale and stated duration text. Include different reference
suffixes, similar digits, two scales, an explicit day count and a calendar-month
expression. Do not convert a month to a day count. Exclude people, signatures,
real locations, retrieved source text and real decision identifiers.

Record fonts, raster dimensions, rendering commands and file hashes. Inspect the
rendered pages against their authoring records before locking inputs. A text-layer
check must verify that image-only fixtures expose no embedded answer text. OCR
receives only the raster, not the authoring file or selectable-text sibling.

## Execution and preflight

The experiment is a separate offline research command, not a collector or report
feature. Real-data loaders and existing report behaviour remain unchanged.

Check the executable and required recognition data before any scored run. A
missing language model produces `not_run_missing_recognition_data`; it is neither
zero accuracy nor a negative OCR result. Orientation/script detection data alone
does not satisfy the recognition-data requirement. Any later recognition-data
installation needs its official provenance, licence and pinned digest recorded.

Run the same fixed pages through ordinary PDF extraction and local OCR. Fix
engine version, recognition data, options, timeout and field-matching rules before
running. Keep raw local output separate from extracted fields and expected values.
Timeout, unreadable output and ambiguous fields remain explicit outcomes; no
plausible field value is invented. No hosted fallback is permitted.

## Evaluation contract

First report field-level exact matches and errors with denominators, separately
for each representation and family. Any normalisation is predeclared; it cannot
erase a leading zero, digit, reference separator or duration unit. No legal stage
or finality is inferred from recognising words.

If categorical accuracy is reported, include constant/majority and seeded random
baselines under the same field contract. Freeze their label inventory, tie rule
and seed before scoring. For this tiny development set, show the errors themselves
and make no generalisation, significance or production-readiness claim.

Measure process elapsed time separately from human inspection time. Fixture
authoring time, recognition time and correction time are different quantities.
No time-saving claim is possible without an observed comparison workflow.

## Gates and outputs

1. Preflight report identifies whether recognition can run.
2. Fixture manifest and matching rules are locked before engine comparison.
3. Per-page results preserve mismatches and failures, including negative findings.
4. A decision note states whether a larger independently reviewed experiment is
   justified. Passing synthetic pages does not enable real-source ingestion.

Before implementation, settle the recognition-data installation and complete the
fixture/matching registration. Human-reviewed real cases, source-use acceptance
and lifecycle controls remain separate gates. No operational accuracy threshold
or product launch decision is inferred from this feasibility experiment.

## Fixed development protocol

Use four labelled fields: decision reference, date, scale and duration. Institution
labels are context only. Extract a value only from exactly one line beginning
with the configured field label followed by a colon. Trim outer whitespace;
preserve case, internal whitespace, punctuation and every digit. Zero matching
lines means missing; multiple matching lines means ambiguous, even if identical.
No matching against the expected value is allowed during extraction.

Use local Tesseract with engine mode 1, page segmentation mode 6 and a 30-second
per-page timeout. Render at 150 dots per inch. Fonts and recognition-data paths
are explicit command arguments. Use one configured recognition language; this
small typographic test does not validate the eventual target-language corpus.

For each field, the majority baseline uses the most frequent authored value
across four families, resolving ties by lexical order. The random baseline uses
the sorted unique authored values; the index is the big-endian SHA-256 integer
of `seed:family_id:field_name` modulo inventory length. Seed is 27092026. Paired
representations receive identical baseline predictions. These are development
baselines derived from the authoring inventory, not learned held-out predictors.

Generate the fixtures, visually inspect all four families in both representations,
then explicitly lock the registration containing file digests, rules, versions,
engine/data/font hashes and runner code digests. Comparison refuses changed
registered files. Raw output, failures, elapsed process times and exact-match
counts remain available per page; failed pages stay in denominators. Use a new
output directory per run. This is an integrity check, not a cryptographic proof
against an operator deliberately replacing both the registration and its lock.
