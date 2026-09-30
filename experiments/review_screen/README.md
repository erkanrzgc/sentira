# Local synthetic review screen

Generate a standalone review page from a locked synthetic OCR experiment:

```powershell
python -m experiments.review_screen.run `
  --fixtures out/ocr-stress-v1 --results out/ocr-stress-results-v1/results.json `
  --output out/review-screen-v1
```

Open the generated `index.html` locally. It embeds source images and candidates; no
server, hosted inference or external resource is needed. Original authoring
answers and baseline predictions are excluded. This is assisted review of
development material, not an independent reference-labelling evaluation.

Inspect each image before selecting a decision. All fields start pending.
Acceptance uses the displayed candidate; correction needs your transcription and
reason; withholding needs a reason. Pending fields are omitted from the exported
decision TOML and remain gaps in the existing field-review workflow. No bulk
acceptance or automatic case-event creation is provided.

Download the decisions before closing or refreshing. Edits live only in browser
memory, and an unload warning cannot guarantee recovery. Validate the downloaded
file with the existing command, retaining the original fixture and result files:

```powershell
python -m experiments.field_review.run report `
  --fixtures out/ocr-stress-v1 --results out/ocr-stress-results-v1/results.json `
  --decisions PATH_TO_DOWNLOADED_TOML --output out/human-review-report
```

The optional start/pause timer records active visible browser-session elapsed
time in a separate JSON download. It pauses when the page is hidden. This is not
field-level correction time, authenticated labour time or a time-saving estimate.
Do not count assistant smoke-test actions as human evaluation. Independent
references, representative layouts and an evaluation protocol remain necessary
before drawing quality or productivity conclusions.

The generator checks the existing registration and image digests before writing
to a new output directory. File hashes bind content, not reviewer identity or
authenticity. Treat the page and downloaded decisions as local development
artefacts; the Python review validator remains the downstream acceptance check.

Verification commands:

```powershell
python -m pytest tests/experiments/test_review_screen.py -q
node --test tests/experiments/review_screen.test.cjs tests/experiments/review_screen_app.test.cjs
```

Node.js is a development check for JavaScript export and timer logic, not a
runtime requirement for the generated page. Cross-language checks explicitly
skip when Node is unavailable. These tests do not replace visual or interactive
browser verification.

Application-event checks run the actual scripts against a small DOM test double
with controlled time and captured download payloads. They check event wiring and
state retention only: no browser is opened, images are not rendered, and native
download or visibility-event delivery is not tested.
