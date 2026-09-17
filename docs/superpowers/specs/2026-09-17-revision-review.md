# Revision-aware scenario eligibility

The operator authorised the next correctness task: withhold scenarios whose
evidence has been revised, while preserving historical reports.

## Cause and bounded repair

The renderer previously displayed revision links without removing old evidence
from eligible scenario support. Storage now computes review-required identifiers
inside the same transaction and cutoff/source-registration boundary as the view.
An observed revision marks its predecessor for review. Support dependencies
propagate that mark; revised counterevidence also gates any scenario referencing it.

The renderer excludes marked records from eligible support and corroboration.
Affected scenario headings, summaries, unknowns and triggers are withheld with an explicit review
message. Still-visible original records remain attributed audit material. A new
versioned question can explicitly reference revised evidence; no automatic
replacement or claim of completed human review occurs.

Synthetic expiry hides content but does not undo an observed correction. The view
retains only derived review identifiers from expired records, not their text.
Future observations do not contribute even a review identifier. This is not a
production deletion policy: required physical erasure and backup lifecycle remain
unimplemented. Retaining these dependencies for real data needs separate approval
under the source-use contract.

Revision links are operator-supplied. The code does not infer corrections from
text or establish that a publisher is authorised to correct another publisher.
Any registered revision conservatively requests review, including a minor edit;
branching revisions never select a winner automatically. Ordinary contradictions
retain the existing contested treatment rather than being interpreted as revisions.

## Verification sequence

Removed the known expected-failure marker and added chain, expiry, indirect-support
and counterevidence cases. Before the fix, five checks failed and four passed.
After the fix, the full suite passed. An additional persistence case checks that
expiry cannot revive old support after reopening the database. Exact final totals
and review results are recorded in CONTINUATION.
