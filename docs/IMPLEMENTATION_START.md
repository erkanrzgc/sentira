# Implementation start proposal

Status: approved for local implementation, 2026-09-13. The user approved the
bounded scope below. Its amendments take precedence over the corresponding
earlier design statements; it does not authorise live collection.

## Objective

Resolve the review findings that affect the first implementation, then build a
small offline foundation whose guarantees can be tested without credentials.
Aggregate-only output, restricted targets, boundary hashing, snapshot-only
counters, official APIs and local inference remain binding.

## Approaches considered

| Approach | Benefit | Cost or limitation |
|---|---|---|
| **Resolve the contracts, then implement the offline foundation** | Produces testable progress while source permissions are resolved | Delivers no live analytical result in the first increment |
| Implement the full Phase 1 immediately | Follows the existing module map | Commits to unresolved replay, retention and scheduling assumptions |
| Start with a local language-model demonstration | Makes text classification visible quickly | Does not settle data access, temporal validity or forecasting quality |

The first approach is recommended. Model experiments follow an independent human
evaluation set; they are not prerequisites for the foundation.

## First increment: reconcile the design

| Decision | Proposed resolution | Acceptance evidence |
|---|---|---|
| Present capabilities versus commitments | Use prospective wording for unimplemented guarantees; distinguish historical measurements from reproducible tests in this repository | README and design documents contain no unsupported present-tense implementation claims |
| Source permissions | Record permitted collection, aggregation, derived metrics, training use and retention separately; an API key is not evidence of permission for every use | A source-use table with retrieved primary sources, dates and explicit unresolved questions |
| Historical visibility | Keep the existing replay restriction; do not infer certified visibility from a surviving corpus alone | A worked page-cap counterexample; exact replay claims restricted to complete recorded histories |
| Discovery and polling | Before discovery, no poll runs. On discovery, coalesce missed due ages into one immediate poll; future ages remain anchored to publication. Log missed ages and actual delivery times | Deterministic schedules for late discovery, coincident ages and restart; no observation is back-dated |
| Pilot registration | Lock a pilot protocol before pilot collection; lock the main registration after the pilot and before confirmatory retrieval | Separate artefact names, input spans and permitted adaptations; pilot data excluded from confirmatory evaluation |
| Pilot size | Use a fixed, stratified small channel sample and a hard quota ceiling before committing to all-channel history | Cost report includes discovery, polling, paging, survival and refresh costs; no unmeasured depth promise |
| Data lifecycle | Separate first observation metadata from refresh/deletion obligations; do not use insert-once text storage to avoid lifecycle requirements | Retention design states what is removed and which historical results cease to be reproducible after removal |
| Identity limits | Treat persistent hashes as within-source linkage, not anonymity; specify minimum contributor counts and text handling before external output | Privacy guarantees distinguish storage, access and publication; no claim that hashing prevents all linkage |

The replay and lifecycle questions are implementation blockers for historical
evaluation, not reasons to weaken the architectural constraints. If past
visibility cannot be established, the confirmatory path uses the existing strict
reader. Any exploratory reconstruction remains separately labelled and cannot be
promoted to confirmatory evidence.

The pilot sample size, quota ceiling and publication suppression threshold must
be specified in their respective registrations before those features execute.
They are outside the offline increment; no live pilot or report is enabled by
this proposal.

## Second increment: offline foundation

Use Python 3.12 and the existing module map. Implement only the following slice
after the revised contracts and implementation plan have been reviewed:

| Component | Responsibility | Failure behaviour |
|---|---|---|
| `core/document.py` | Immutable document envelope and declared field classes; counters excluded | Reject malformed timestamps, undeclared fields and prohibited identifier fields |
| `core/identity.py` | HMAC-SHA256 boundary with explicit platform and identifier-kind separation | Missing key prevents ingestion; raw identifiers never enter diagnostics |
| `config/schema.py` | Restricted target types and validation of the initial configuration | Reject unsupported types rather than silently coercing them |
| `storage/schema.py`, `repository.py` | Documents and separate snapshots; storage-owned observation clock | Failed writes roll back; callers cannot back-date observations |
| `storage/asof.py` | Strict point-in-time reads through one storage boundary | Later observations and later snapshots remain invisible |

Flow: synthetic input -> boundary hashing and validation -> storage -> strict
as-of read -> test assertions. Synthetic inputs are explicitly labelled and
separate from recorded API fixtures. No source adapter, forecast, tone score or
client report is included in this increment.

The initial schema is for disposable synthetic data. Production ingestion remains
disabled until retention, refresh, deletion and access controls are implemented
and their source-use conditions are resolved. The foundation is not described as
complete Phase 1 or as production-ready privacy enforcement.

### Required checks

- Identical raw identifiers differ across platforms and identifier kinds.
- Missing keys fail before any ingestion or persistence.
- Raw identifiers and cumulative counters cannot enter a document or its table.
- Disallowed target types fail configuration validation.
- Observation timestamps come from an injected storage clock.
- At time T, future documents and snapshots cannot affect the strict read result.
- A failed write leaves no partial document/snapshot state.
- No non-storage module imports the database driver.
- Tests make no network requests and use no personal data.

Passing these checks demonstrates the listed offline contracts only. It makes no
claim about API behaviour, model accuracy, legal compliance or forecasting skill.

## Verified source updates

Retrieved on 2026-09-13:

- The official [quota table](https://developers.google.com/youtube/v3/determine_quota_cost)
  assigns search a separate default bucket of 100 calls per day, at one unit per
  call. The registered endpoint exclusion remains unchanged; its old cost rationale
  requires correction. This is verified documentation, not measured project quota.
- The [derived-metrics policy](https://developers.google.com/youtube/terms/derived-metrics-policy)
  describes conditional permission for additional analytics and up to 36 months
  of storage for accepted statistical and derived metrics. Comment text remains
  subject to the 30-day refresh/deletion policy. These provisions do not establish
  that this project's proposed use has been accepted.

## Review and completion

The resolutions and bounded offline scope have been reviewed and approved.
Reconcile the existing documents and execute the detailed implementation plan.
Completion of the first code increment requires the named checks, a reproducible
local test command and an updated continuation record of unresolved blockers.
Publication and remote Git operations are separate from this local work.
