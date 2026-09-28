# Reviewed-field candidate eligibility

Status: bounded offline continuation of the synthetic field-review workflow.
This increment lists eligible candidate fields; it does not create case events.

## Why a separate gate

Explicit review is necessary but does not establish a procedural event, legal
effect or authenticity. Automatically mapping a document's generic date to an
event date would add an unsupported meaning. A candidate list preserves the
reviewed field and page identity without making that inference.

Three alternatives were considered: directly populate case events, retain only
the review report, or add a narrow eligibility gate. The gate is selected because
it can expose revision and type failures without introducing event semantics.

## Inputs and temporal contract

Rebuild the existing packet from its locked synthetic fixtures and OCR results,
then recompute reviewed rows from the actual decision TOML. Do not trust an edited
standalone reviewed-result file. A separate external context TOML contains:

- `synthetic = true`, the canonical packet digest and canonical decisions digest;
- an explicit timezone-aware `reviewed_at` for this synthetic simulation;
- `permitted_fields`, a subset of decision, date, scale and duration;
- page bindings identifying the source version inspected during review;
- source versions with unique ID, page ID, timezone-aware observation time,
  image SHA-256 and status `available`, `unavailable` or `withdrawn`.

Each page binding must refer to an available version whose image digest matches
the packet. It must be the latest registered observation at or before review.
Version IDs are unique; two observations of the same page cannot share a timestamp.
Every packet page has exactly one binding; no foreign page or binding is admitted.
All observations and review times are operator-authored simulation data, not a
durable collection clock or an authenticated historical review record.

At cutoff T, only review and source observations at or before T are visible. A
later source observation cannot change an earlier view. If the latest visible
source version differs from the bound reviewed version, require fresh review,
even when the bytes have reverted to the old digest. Unavailable and withdrawn
sources suppress values. A new review requires a new context and an explicit
decision binding; this snapshot workflow is not an append-only audit ledger.

## Field contract

Only accepted/corrected review rows can be eligible. Pending or withheld rows
remain gaps. Fields outside the external permitted subset remain gaps. Structural
checks are conservative and do not repair values:

| Field | Accepted structure | Prohibited inference |
| --- | --- | --- |
| decision | Digit groups separated by `.`, `/` or `-`, with at least one separator | Identity/authenticity of a real decision |
| date | Exact valid `YYYY-MM-DD` calendar date | Event date, approval date or observation date |
| scale | `1/` followed by a nonzero decimal denominator | Permitted use or entitlement |
| duration | Positive decimal integer followed by ` days`, or `one calendar month` | Calendar conversion, closure or finality |

Preserve every accepted character, including leading zeros and separators.
Malformed values receive `invalid_value`; they are not fixed from references.
Eligible output says `eligible_candidate`, not verified evidence. No probability,
accuracy or independence count is produced.

## Verification and outputs

Tests cover future-source invariance, pre-review suppression, changed/reverted
version invalidation, withdrawal/unavailability, duplicate timelines, mismatched
bindings, unsupported fields and impossible calendar dates. A new CLI under
`experiments/eligibility/` writes fresh JSON/Markdown directories, with exact
input file hashes; it cannot modify case records or replace existing output.
Use the already measured synthetic stress packet and simulated decisions for
the demonstration. Leave both previous experiment and review artefacts intact.

Each output row distinguishes the reviewed version and its image digest from
the latest visible version and its image digest. Neither JSON nor the report
may pair a later version identifier with the reviewed image's digest.
