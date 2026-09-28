# Reviewed-field eligibility implementation plan

> **For agentic workers:** Use subagent-driven development and independent review.

**Goal:** Suppress stale or structurally invalid reviewed fields before any event mapping.

**Architecture:** Standard-library eligibility functions recompute field review,
validate external synthetic version context and select source visibility at a
cutoff. A separate CLI emits candidate rows only; existing OCR and case modules
remain unchanged.

- [x] Add `experiments/eligibility/core.py` and focused tests. Test first: valid
  candidate, changed/reverted version, future invariance, unavailable/withdrawn
  source, future review, invalid date, preserved calendar-month wording and
  configuration/decision digest mismatches. Then implement the bounded contract.
- [x] Add `experiments/eligibility/run.py` and CLI tests for no output replacement,
  invalid inputs failing before output, and recording the exact context digest.
- [x] Create external synthetic context against the existing stress packet.
  Demonstrate an early eligible view and a later revision-required view without
  accepting replacement values automatically. Preserve all prior artefacts.
- [x] Run complete tests and Ruff; obtain independent review and update continuation.
  The final run passed 384 tests; both review findings were corrected and rechecked.

Integration procedure: commit and fast-forward locally, then push the tested
increment under the current permission and verify the remote SHA. Git records
the resulting commit identity; no release or deployment is part of this plan.

Use the project Python 3.12 test environment. Neither tests nor the command invoke
native OCR, access the network or create a live-source collector.
