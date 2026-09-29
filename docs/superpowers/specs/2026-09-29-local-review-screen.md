# Local synthetic review screen

The next bounded increment makes the existing review packet usable without hand
editing TOML. A generated standalone HTML file shows registered source images
beside OCR candidates. It remains an assisted development review, not an
independent reference-labelling experiment or a product accuracy evaluation.

Alternatives considered: a local HTTP application offers persistence but adds a
server and mutation boundary; a desktop application adds packaging dependencies.
A standalone page is selected for this first reversible workflow.

The Python generator rebuilds the packet from locked fixtures and results using
the existing API, verifies each embedded image against its packet digest and
embeds only that packet and image bytes. Authoring answers and baseline results
are excluded. Output must be a fresh directory; validation completes before it
is created. No network or OCR calls occur. CSS and JavaScript live in separate
repository files but are embedded into the generated HTML for offline use.

Every field defaults to pending. Accept is available only for a nonempty found
candidate from successful recognition. Correct requires an explicit single-line
value and reason; withhold requires a reason. The same limits as the Python
decision validator apply. Switching back to pending omits that field from export.
Navigation retains decisions in browser memory. No bulk acceptance is provided.
The exported TOML must be accepted by the existing apply_decisions function and
must retain the exact packet digest. Download does not update the case ledger.

Show one source page and its fields at a time, with labelled form controls,
previous/next controls, page count, review progress and image zoom. Render all
untrusted values as text. Embedded JSON must not permit script-tag termination.
No external resources, fetch, telemetry or automatic upload is permitted.

An explicit start/pause timer measures active visible browser-session elapsed
time; hiding the page pauses it. Export its milliseconds in a separate JSON file
bound to the packet. Call it browser session time, not correction time, labour
saving or authenticated human review. Refresh loses in-memory decisions; display
this limitation and an unload warning for edits. No persistence is claimed.

Verify packet binding, image tampering, injection escaping, fresh-output behaviour,
decision TOML round-trip including escapes and omission, and deterministic timer
behaviour. Perform a browser smoke test using synthetic fixtures without counting
assistant actions as human evaluation. Independent review precedes integration.
