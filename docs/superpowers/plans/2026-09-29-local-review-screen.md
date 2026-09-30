# Local review screen implementation

Use subagent-driven development with independent review. Reuse the attached
worktree and the existing locked synthetic stress fixture outputs.

1. Add experiments/review_screen generator, external template/CSS/JavaScript and
   focused tests. Keep decision export compatible with field_review.
2. Exercise browser-neutral JavaScript logic and Python input/output boundaries.
3. Generate a fresh local demo, visually inspect it and smoke-test decisions.
4. Run full tests and Ruff, review code independently, update continuation, then
   commit, integrate and push under the existing authorisation. Verify remote SHA.

No live data, inference service, source collector or model training is included.

Execution record: generator/assets and tests implemented; 392 Python tests and
two Node tests passed, with Ruff clean and independent review complete. The final
generated demo is `out/review-screen-v2/index.html`. Browser smoke testing remains
open because tool policy refused local-file navigation and prohibited workarounds.
Do not mark step 3's visual/interactive portion complete from unit-test results.

Follow-up on 2026-09-30: the user supplied screenshots and an exported decision
file, and the Python validator confirmed the assisted accept/correct hand-off.
Add isolated Node application-event tests for navigation retaining drafts,
pending omission, invalid export rejection, withholding, visibility pause and
unload warnings. Execute the actual application scripts against a minimal DOM
test double with controlled time and captured download payloads. This does not
open a browser or establish rendering, real downloads or browser event delivery.
Independently review the harness and verify selected in-memory mutations are
detected before recording the additional software guarantees.
