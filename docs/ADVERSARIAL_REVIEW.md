# Adversarial briefing review

Measured on 2026-09-14 against the deterministic synthetic briefing pipeline.
These checks exercise explicit fixture metadata, not automatic understanding of
real-world contradictions or forecasting accuracy.

| Check | Observation | Result |
|---|---|---|
| Explicit counterevidence | Opposing evidence text and contested status remain visible | Passed |
| Repeated origin | Twenty copies retain one supporting origin | Passed |
| Later correction, historical view | Earlier report remains byte-identical; correction appears only later | Passed |
| Later correction, current scenario | A scenario using the earlier claim remains displayed after its withdrawal is supplied as a revision | Failed |

Initial execution: three passed, one failed. The failed expectation is retained
as a strict expected failure in `tests/briefing/test_adversarial.py`, with its
reason stated explicitly. This is an unresolved product limitation, not a passing
acceptance criterion. No renderer behaviour was changed in this review.

## Finding

The renderer displays a revision link but still includes the superseded record in
eligible scenario support. In the fixture, an institution withdraws a consultation
notice; the current report nevertheless retains the scenario heading that the
timetable proceeds without a substantive date change. Showing the new evidence
elsewhere in the report does not prevent this misleading presentation.

The test requires the old substantive heading to be withheld for review. It does
not require interpreting arbitrary correction text or silently rewriting a frozen
question. A bounded remedy should mark affected support as requiring review when
an eligible revision is visible, preserve the original record for audit, and
withhold dependent draft text until explicitly reviewed. Historical views must
remain unchanged. Chained revisions, expired revisions and later counterevidence
need explicit rules before that change is implemented.

## Limits and next work

Contradiction and origin relationships were supplied in fixtures. The system did
not discover them by reading text. A correctly supplied origin group is assumed;
the experiment does not establish publisher independence. Human review of the
three earlier reading drafts established usefulness, not these software properties.

Fix revision-aware scenario eligibility before treating current briefings as
reliable under corrections. Then rerun the failing regression without its expected
failure marker, together with historical invariance and expiry cases. Model
selection and training remain deferred.
