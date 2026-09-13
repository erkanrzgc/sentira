# Source-use decisions

Status: design record, checked 2026-09-13. No live ingestion is enabled by the
offline foundation. A documented API capability is not permission for every
downstream use. This record is not a legal opinion or a platform approval.

## Video-platform API

The following primary-source text was retrieved during the project review:

| Use | Verified source statement | Project decision |
|---|---|---|
| Collection | The API documents official endpoints and quota allocation | Use registered endpoints only; project credentials and actual allocation remain unmeasured |
| Aggregation | General developer policies restrict aggregation across content owners | Acceptance of the proposed multi-channel use has not been established |
| Derived metrics | Additional analytics may be permitted under the policy amendment; comment sentiment is an example | Confirm the exact aggregate topic/target use under the applicable approval process before enabling it |
| Sensitive inference | The amendment prohibits protected-attribute profiling or inference about an audience or creator | Do not infer audience political affiliation; aggregate expressed stance still requires use-specific review |
| Training | Permission for analytical output does not itself establish training rights | Teacher labelling, student training and retention of training examples remain unresolved |
| Raw text | Comment text remains subject to the 30-day refresh/deletion policy | An immutable historical corpus is not the default storage design |
| Statistical and derived metrics | Accepted uses may retain specified statistical and derived metrics for up to 36 months | No such acceptance is established for this project; distinguish metrics from raw text |
| Deletion | General policies require a deletion mechanism and timely fulfilment | Define linkage, deletion propagation and backup expiry before real ingestion |

Sources: [Developer policies, III.E and III.L](https://developers.google.com/youtube/terms/developer-policies),
[Additional derived-metrics and storage policy](https://developers.google.com/youtube/terms/derived-metrics-policy),
[Quota table](https://developers.google.com/youtube/v3/determine_quota_cost).

The quota table gives search its own default bucket of 100 calls per day, at one
unit per call, and 10,000 daily units combined for other endpoints excluding the
separately allocated upload method. This is verified documentation, not a
measurement of project allocation. Search remains outside the registered endpoint
set. Quota availability and use permission are separate questions.

## Other sources

| Source | Decision before collection |
|---|---|
| Publisher feeds | Register the feed and permitted fields; review publisher terms for retention, aggregation and redistribution. Feed availability does not establish unrestricted reuse. No training on news text is planned |
| Event archive | Verify the chosen archive's licence and retention conditions before downloading it; candidate metadata does not become independently verified ground truth |
| Other social platforms | Disabled and outside this increment; historical access/pricing notes are not current authorisation |

No new source-specific permission is asserted for these rows. They are unresolved
decisions, not verified grants of rights.

## Lifecycle and temporal correctness

Preserve the first observation timestamp without promising perpetual preservation
of its content. Any future production design must reconcile source refresh,
deletion, derived-data retention and backup expiry with as-of reproducibility.
Deleting a required observation can make an old result unreproducible; report that
loss rather than retaining prohibited content or silently substituting new text.

Hashes remain linkable within their scope. They do not remove rights or lifecycle
obligations. Access restrictions, text redaction, minimum contributor counts and
protection against differencing related outputs must be implemented before client
reporting. No numerical suppression threshold has been approved or implemented.

## Conditions for a live pilot

Record the permitted use, relevant acceptance or rights evidence, authorised
fields, retention schedule, refresh/deletion implementation, registered collection
policy and quota ceiling before starting. An environment variable that contains an
API key satisfies only authentication. Keep genuine source-response fixtures
separate from synthetic fixtures and process them through the same identity
boundary; no raw personal identifiers may enter the repository.
