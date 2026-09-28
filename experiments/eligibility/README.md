# Reviewed-field candidate eligibility

This offline synthetic experiment checks whether an explicitly reviewed field
can remain a candidate at a specified observation cutoff. It rebuilds the locked
field-review packet and reapplies the supplied decisions. It does not consume an
editable reviewed-result file or create case events.

```powershell
python -m experiments.eligibility.run `
  --fixtures out/ocr-stress-v1 --results out/ocr-stress-results-v1/results.json `
  --decisions out/field-review-packet-v1/simulated-decisions.toml `
  --context out/eligibility-context-v1.toml `
  --cutoff 2030-09-02T00:00:00+00:00 --output out/eligibility-early-v1
```

The context is external TOML with exactly `synthetic = true`, `packet_sha256`,
`decisions_sha256`, `reviewed_at`, `permitted_fields`, `bindings` and `versions`.
The two bindings are canonical JSON SHA-256 digests computed with
`experiments.field_review.core.packet_digest`. Exact input-file byte digests in
the CLI output serve a separate provenance purpose.

Each packet page needs one binding containing `page_id` and `version_id`. Each
version contains `id`, `page_id`, `observed_at`, `image_sha256` and `status`.
Use timezone-aware ISO timestamps. Status is `available`, `unavailable` or
`withdrawn`. The bound version must be available, match the registered image,
and be the latest observation at the declared review time. Foreign pages,
duplicate identifiers and tied observation times are rejected.

At the cutoff, future review is unavailable and future source observations do
not affect the earlier view. A changed version requires fresh review, even if
its bytes revert to the original digest. Unavailable or withdrawn sources
suppress values. Pending and withheld fields remain gaps; the external permitted
field list can further restrict eligibility.

Structural checks preserve characters without repairing values: decision
references require separated digit groups; dates must be valid `YYYY-MM-DD`;
scales require `1/` and a positive decimal denominator; durations require a
positive integer followed by ` days`, or exactly `one calendar month`.
Calendar months are never converted to a number of days.

`eligible_candidate` means these mechanical checks passed. It does not establish
authenticity, a procedural event date, legal effect or forecast value. Review and
observation times remain caller-authored simulation data. Persistent history,
authenticated review, source lifecycle enforcement and representative independent
evaluation remain unimplemented. Output directories must be new.

Rows distinguish `reviewed_source_version_id` and `reviewed_image_sha256` from
`latest_source_version_id` and `latest_image_sha256`. A changed source must not
be displayed beside the old image digest as though they were one observation.
