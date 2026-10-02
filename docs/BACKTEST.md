# Section 3 — Backtest protocol, phase order, first implementation files

*Design Section 3, approved 2026-09-12. Figures are labelled* calculated,
measured *or* verified. *Constants marked* proposed *are fixed only when the
pre-registration is locked (§A.9). Binding inputs:
[ROADMAP](ROADMAP.md) Sections 1–2 and [FORECASTING](FORECASTING.md). The design
was reviewed adversarially before approval; the review dispositions are held with
the internal research material.*

---

## Implementation amendment — 2026-09-13

The approved [implementation scope](IMPLEMENTATION_START.md) qualifies this
protocol. The first code increment implements only strict observation-time reads
on synthetic data. The tables below map future guarantees as well as that subset;
their presence is not evidence that Phase 1 exists or that history is backtestable.
Source permissions and lifecycle conditions are tracked in [SOURCE_USE](SOURCE_USE.md).

Historical replay requires evidence of past visibility. A surviving corpus alone
cannot provide it: at a 1,000-thread cap, a row originally behind 1,000 newer rows
was not returned. If 200 newer rows disappear before retrieval, replay on survivors
can incorrectly admit it. This is a constructed counterexample, not a measurement.
Exact replay tests therefore require complete recorded visibility histories.
Survivor-only reconstruction is exploratory, not confirmatory evidence; strict
prospective observations are the confirmatory route when visibility is unknown.
Neither a survival percentage nor a fixed p90 latency proves exact historical
visibility. Report discrepancies on live controls instead of asserting equality.

Discovery precedes polling. No poll runs before discovery. At discovery, missed
due ages are coalesced into one immediate poll; future ages remain anchored to
publication. If no age is due, wait for the next age. At a restart, coalesce missed
due jobs similarly, preserving completed-job identities to avoid duplicate work.
Record missed ages, scheduled time and actual delivery separately. An immediate
catch-up after the last registered age is a live observation only; it does not
retroactively make comments replay-visible under the earlier age schedule.

Registration order is: lock `pilot.yaml` (sample, strata, schedule, quota ceiling,
adaptation rules and pilot span) -> bounded pilot -> lock main registration v1
(including D0 and O1) -> retrieve the pre-origin span -> lock measured addendum ->
confirmatory evaluation. Pilot data cannot enter confirmatory test folds. Use a
small fixed stratified sample rather than the former all-channel ten-week pilot.
The numerical pilot budget must be registered before execution; none is enabled
by the offline increment. The pilot report includes refresh and deletion costs.

First observation wins for provenance, not for perpetual content retention.
Production refresh/deletion rules take precedence over reproducibility; after
required deletion, identify affected results as no longer reproducible. The
offline database is disposable synthetic storage and implements no production
lifecycle. Production ingestion remains disabled until that design is resolved.

A synthetic, offline subset of Phase 1 now exists: a locked surge registration,
episode detection on strict as-of series and per-cell counts. Its deviations
from the file list below (TOML, content digests, a fixed calendar offset and
proposed measurement rules) are recorded in the
[surge-counting design](superpowers/specs/2026-10-02-surge-counting.md).
The quota policy, ledger and metered client also exist offline, with synthetic
transports only; the ledger sits in `storage/quota.py` rather than
`collectors/quota.py`, as recorded in the
[quota-ledger design](superpowers/specs/2026-10-02-quota-ledger.md).
The polling schedule and replay times of policy *P* exist as pure functions over
synthetic inputs; see the
[collection-policy design](superpowers/specs/2026-10-02-collection-policy.md).
The quota arithmetic of §B is reproduced in code by a cost projection over the
same schedule; its volume inputs remain the unmeasured assumptions of §D. See the
[cost-projection design](superpowers/specs/2026-10-02-cost-projection.md).

## 0. The point-in-time rule, reconciled with historical retrieval

### 0.1 The conflict

ROADMAP Section 1 states that a feature computed for time *T* reads only rows
observed at or before *T*. Every historically retrieved row carries
`observed_at` = the retrieval date, so for every past *T* the rule admits none of
it and no retrospective backtest exists.

The two binding documents already disagree: FORECASTING (leakage control 1)
permits point-in-time state to be re-derived from items with `published_at ≤ t`.
The rule below reconciles ROADMAP to FORECASTING and then tightens both.

### 0.2 Field classes

Every stored field belongs to exactly one class, declared once in
`core/document.py` and checked against the schema in test.

| Class | Fields | Visible to a feature at *T* |
|---|---|---|
| **Immutable** | `doc_hash`, `kind`, `source`, container (video, channel) id, `parent_hash`, `author_hash`, `published_at` | `observed_at ≤ T`, **or** replay-visible by *T* (§0.3) |
| **Edit-mutable** | comment text | as above, **and** `updated_at ≤ T` |
| **Unversioned mutable** | video title and description, channel metadata | only if `observed_at ≤ T` |
| **Cumulative counter** | view, like, reply and comment totals | only as a `snapshots` row with `observed_at ≤ T`. **No carve-out** |
| **Provenance metadata** | `observed_at`, `updated_at`, `provenance`, censoring and completeness flags | readable by the reader only; never by a feature |

Supporting rules:

- **`observed_at` is stamped by the storage clock** at insert and is never accepted
  from a caller. **First observation wins**: a later retrieval of a document
  already stored never rewrites it.
- **Counters are re-derived, never read.** A historical "count as of *T*" is a
  tally of visible items. A retrieval run's counters are stored as snapshots
  stamped with the retrieval date and are therefore invisible to every earlier *T*
  without a special case.
- **Identifiers are hashed.** Comment and parent identifiers are stored as
  HMAC-SHA256 under the same key as the author hash. A platform identifier for an
  utterance is a live handle: if a single documented lookup by comment id returns
  the author's channel, a raw id column would make the hashing guarantee nominal
  (§D.3). Hashing costs nothing — matching across retrievals works on keyed hashes
  — so it is adopted by default rather than after the exposure is confirmed.
  Container identifiers (video, channel) stay raw; they are not persons.
- **Strict mode.** The reader also offers the literal Section 1 rule
  (`observed_at ≤ T` only), used to measure the cost of reconstruction (§A.8).
- **Single read path.** `storage/asof.py` is the only reader of `documents` and
  `snapshots`; no module outside `storage/` imports the database driver.
- **Reconstructed flag.** A row visible at *T* whose `observed_at` > *T* is
  *reconstructed at T*. The flag is a function of (row, *T*) computed by the
  reader, not a stored property; it propagates as `share_reconstructed` into every
  series cell, figure and report and cannot be cleared downstream.

### 0.3 The replay rule

A latency quantile is not a coverage rule. Live collection reads each video a
bounded number of times; comments arriving after the last read are never observed
live, so a rule of the form "visible once published at *T* − λ" would admit, in
the reconstructed era, material no deployable system would ever have held. The
reconstructed series would then be a different variable from the live one, and
they would differ most on exactly the heavy-tail videos that define surges.

**A retrieved row is visible at *T* only where the registered live-collection
policy, applied to the row's own publication time, would have fetched it by *T*.**

The policy *P* is registered in v1 and is the same object the live collector
executes:

| Element | Registered value (*proposed*) |
|---|---|
| Discovery | Upload-playlist enumeration per channel every 6 h |
| Thread polls | At video ages 1 h, 6 h, 24 h, 72 h, 7 d, 30 d |
| Paging | Newest-first, stopping at the last-seen thread; at most *C* = 10 pages (1,000 new threads) per poll |
| Job latency λ | p90 of `observed_at` − scheduled poll time, measured on ≥ 7 days of live running, locked in the measured addendum |

For a retrieved comment *c* on video *v*, the replay time *R*(*c*) is the earliest
`poll + λ` at which *P* would have returned it, given the publication times of all
comments on *v*; *R*(*c*) = ∞ where no poll would have reached it — posted after
the last poll age, or beyond the page cap at every poll. At *T*, *c* is visible iff
*R*(*c*) ≤ *T*. Live rows are visible iff `observed_at ≤ T`, because that is what
actually happened.

Three consequences are stated rather than hidden:

1. Rows with *R* = ∞ enter no T1 feature or label at any *T*. They remain available
   for descriptive measurement (T2), flagged.
2. Information arrives in **lumps** at poll times. A deployed system learns of a
   surge at a poll, not at a comment. §A.2 makes that the conditioning instant.
3. Test exact replay on complete recorded visibility histories. On real
   re-retrievals, measure visibility differences; deleted rows, moderation,
   discovery delays and variable job latency can prevent exact reconstruction.

The carve-out applies only to `UTTERANCE` rows from a source with a registered
retrieval path. **`PUBLICATION` rows are visible only where `observed_at ≤ T`**: a
publisher-supplied timestamp is not evidence that the item was retrievable, and
feeds have no history for the carve-out to serve.

### 0.4 What is and is not allowed

| Allowed at *T* | Not allowed at *T* |
|---|---|
| Counting retrieved top-level comments replay-visible by *T* | Any platform counter read from a retrieved object, or any snapshot with `observed_at > T` |
| Text of a retrieved comment with `updated_at ≤ T`, for topic assignment | Text edited after *T* — the item is absent from every topic series at *T*; the withheld share is reported |
| Author hash of a visible item, for integrity screening computed as of *T* | A retrieved video title or description, for any purpose |
| Snapshots written by live collection with `observed_at ≤ T` | Back-dating `observed_at`, or admitting a row by a publisher-supplied date |
| Statistics fitted within the training window; registered constants | Any statistic, model or vocabulary fitted on data after the training window closes |

Two scope consequences follow. **Topic assignment uses comment text only**, for
live and retrieved rows alike, so the series definition does not change at the
provenance boundary. **`public_engagement` in any backtest is the count of
top-level comments**; reply, view and like totals are counters and are
forward-only.

### 0.5 Residual biases the rule cannot remove

| Bias | Direction | Handling |
|---|---|---|
| Deleted and moderated items absent from retrieval; held-for-review comments never visible | Undercount, plausibly heaviest in heated episodes | Survival measured against the live control, printed with every reconstructed figure, with its direction (§A.8) |
| Channels closed since retrieval; per-channel reachable depth differs | Composition drift | Common-depth history start; channel entry and exit are registered cut-offs; reachable starts reported |
| Taxonomy and channel list written today, with knowledge of the past agenda | Hindsight in feature space | Standing institutional topics only; selection rules that may reference no counter and no metric observed after *D₀*; both frozen and hashed before retrieval. Irreducible for reconstructed results — only prospective evaluation is free of it |
| A retrieved "raw" series has already been filtered by the platform | Understates the raw-versus-cleaned gap | Reconstructed raw series are labelled *platform-filtered as of the retrieval date* |

---

## 1. Candidate retrospective and forward-only components

| Component | Retrospective history | Status |
|---|---|---|
| `public_engagement` — top-level comment count | Reconstruction is conditional on historical visibility evidence; depth **not yet measured** | Survivor-only reconstruction is exploratory; use strict prospective observations for confirmation when visibility is unknown |
| `public_engagement` — views, likes, reply totals | None (counters) | **Forward-only** |
| `tone` | Reconstructable for text not edited after *T* | Descriptive only; decoupled from forecasting (sentiment scores at chance for growth prediction — *verified for photo-reshare cascades; transfer to this platform and language unmeasured*). Not produced before the gold standard exists |
| `media_attention` | None: feeds carry the current window only (*measured*, 11 of 11 working feeds) | **Forward-only** from the first day of feed collection |
| `divergence` | None | **Forward-only**; evaluable once `media_attention` reaches its own positive floor |

Integrity-cleaned variants inherit the status of their parent series.

**The global event database does not fill the gap.** On the one day measured,
domestic outlets supplied 9.0% of the jurisdiction's rows in the English-language
stream and 37.7% in the translated stream (*measured*, n = 1 day); consult and
public-statement codes were 46% of the translated stream (*measured*).
Target-language coverage begins 2015-02-19 (*verified*) and raw volumes are not
comparable across years (*verified*). It measures foreign attention to the
jurisdiction rather than the domestic agenda, and serves only as a candidate
generator for the curated event log (§A.10).

**Consequence.** The only lever on forward-only history is to start collecting.
Feed collection therefore begins on day one of Phase 1, although no feed-derived
series is built until Phase 5.

---

## A. Backtest protocol

### A.1 Evaluation targets

| # | Target | Question | Role |
|---|---|---|---|
| T1 | **Conditional growth** | An episode has reached excess size *k*; will it reach 2*k* within horizon *H*? | Primary; the only foresight claim |
| T2 | **Retrospective event impact** | How far did a logged event displace engagement, and for how long? | Descriptive measurement |
| T3 | **End-to-end known-event check** | Does the series open an episode at the logged date of a known event? | Pipeline validity |

Detection of subjects not yet in motion is not a target (FORECASTING, negative
finding 1).

### A.2 Unit of analysis and the conditioning instant

**Topic × interval.** Topics come from the declared taxonomy, assigned by a lexical
rule set frozen and hashed before confirmatory retrieval. Assignment is **single-label** by a
registered priority rule: multi-label assignment would let one event open several
episodes sharing the same comments, and *K*min could then be reached on duplicated
evidence. Episodes that open within 24 h of one another and share more than a
registered share of comments are reported as a co-onset cluster.

**The hour is the reporting grid; the poll is the conditioning instant.** All
online quantities — trailing counts, onset, *t_k*, every feature, every alert — are
computed on `as_of(T)`, evaluated at hourly ticks. Baselines use daily totals on
the local calendar day (timestamps stored in UTC); the daily grid alone would
collapse *k* and 2*k* crossings into one interval and destroy lead-time
resolution, since attention lifetimes are measured in hours (*verified for
trending hashtags on another platform*).

Because information arrives in lumps (§0.3), the as-of series can pass *k* and 2*k*
in the same tick. That is a property of a polling system, not an artefact:

- **τ_k**, the conditioning instant, is the first hourly tick at which the as-of
  series shows *S* ≥ *k*. Features read only rows visible at τ_k.
- **Overshoot**, *S*(τ_k)/*k*, is reported as a distribution and used as a
  stratifier. It is legitimate knowledge: every model and every baseline sees the
  same as-of state.
- **Detected at crossing.** Episodes already at *S* ≥ 2*k* when first known admit no
  forecast. They are excluded from the T1 population and reported as a share — a
  product finding in its own right: the fraction of surges that are only visible
  once they have already doubled.
- **Lead time** runs from τ_k to the tick at which the as-of series shows 2*k*, never
  to the publication time of the crossing comment.

### A.3 Operational surge definition

A cascade starts from zero; a topic series has a drifting background level. Growth
is therefore net excess over a trailing baseline frozen at onset.

| Term | Definition (*proposed* values in brackets) |
|---|---|
| Baseline *b*(*d*) | Median daily count of the topic over the 28 days ending *d* − 1; MAD as scale. Strictly past |
| Onset *t*₀ | First tick where the trailing-24 h as-of count ≥ *m*·*b* [*m* = 2] and ≥ *c*min, the topic has no open episode, and ≥ *R* [72 h] has elapsed since the last episode ended. *b*\* = *b* at onset, frozen |
| Size *S*(*t*) | Net excess: visible comments in [*t*₀, *t*] minus *b*\*·(*t* − *t*₀)/24 h |
| *k*, τ_k | *k* = κ·*b*\* [κ = 1], floored at *k*floor comments; τ_k per §A.2 |
| Positive | *S* ≥ 2*k* at some tick in (τ_k, τ_k + *H*] |
| Negative | Horizon fully observed, *S* < 2*k* throughout, including episodes that end early |
| Censored | τ_k + *H* beyond the end of data, or a contributing video that failed the completeness check (§A.9). **Excluded, not negative**, and counted |
| Episode end | Trailing-24 h count below the **current** rolling baseline for 24 consecutive hours, or a registered maximum duration [2*H*], whichever comes first |
| Horizon *H* | Smallest of {24, 72, 168} h that is ≥ 3 × the median episode half-life of the hourly excess rate, measured on the pre-origin span; else 168 h |
| *c*min, *k*floor | Set by registered rules from the median and MAD of the pre-origin hourly volume distribution; label-free. Computation order registered: *c*min and *k*floor first, then episodes, then the half-life and hence *H* |

The end rule is tied to the *current* baseline deliberately. With an end rule tied
to the frozen baseline, a topic that settles at a permanently higher level never
ends its episode and accumulates net excess indefinitely: at *b*\* = 100/day
settling to 115/day, *S* reaches 2*k* after about 160 h (*calculated*), so at
*H* = 168 h a level shift is scored as growth. Every result reports the share of
positives reached only after the rolling baseline had already moved above *b*\*.

**Balance is measured, not assumed.** Cheng's 50% arises from thresholding at the
empirical median; a fixed 2*k* label need not be balanced. Every result reports the
positive share among episodes reaching *k*, and the unconditional stream rate.

**Grid** (all cells reported; none promoted after results are seen):
κ ∈ {0.5, 1, 2, 4}, *m* ∈ {1.5, 2, 3}, *H* ∈ {24, 72, 168} h. Performance as a
function of κ is itself a finding (performance rises roughly linearly in *k*,
*verified for photo-reshare cascades*). Burst-state detection is a supporting
descriptor, never a label.

**Primary cell and fallback.** Primary: κ = 1, *m* = 2, *H* by rule. With fewer
than *K*min positives the registered fallback is κ = 0.5; with fewer than *K*min
negatives, κ = 2; *m* and *H* unchanged. If both classes are short, the registered
outcome is "not backtestable on current history". The per-cell share of episodes
where *k*floor binds is reported, because κ has no effect on those topics and the
fallback silently changes the topic mix otherwise.

### A.4 Baselines (always run)

| Baseline | Score for an episode at τ_k |
|---|---|
| **Baserate** | Share of admissible episodes in the same cell that reached 2*k*, among those with τ_k in the trailing 90 days; per topic where it has ≥ 10, pooled otherwise |
| **Persistence** | Implied doubling ratio: net excess rate over the last min(τ_k − *t*₀, 24 h), extrapolated across *H* and divided by *k*, mapped to a probability by a one-parameter logistic fit on the training window |
| **Timing-only** | Logistic regression on: τ_k − *t*₀; net excess rate in the second half of [*t*₀, τ_k]; ratio of second- to first-half rate; overshoot at τ_k; hour of week. Specification fixed in registration v1 |

Timing-only is the model to beat. A content or source feature set is admitted only
where it improves on timing-only with a paired interval excluding zero (temporal
features lie within 0.025 of the full model, *verified for photo-reshare
cascades*). Tone features are not admitted.

**Admissibility.** One function, `admissible(episode, origin) := τ_k + H ≤ origin`,
governs the baserate, the persistence fit, the calibration map and the alert
threshold. Admitting an episode as soon as its *outcome* resolved would enrich the
recent part of every training window in positives — a positive resolves at its 2*k*
crossing, a negative only at τ_k + *H* — inflating the baserate and overshooting
the target alert volume.

### A.5 Walk-forward scheme

| Element | Rule |
|---|---|
| Registered constants | History start *D*₀ and first origin *O*₁ = *D*₀ + 118 d (28 d burn-in + 90 d training) are fixed in v1 after the separately registered pilot and before confirmatory retrieval (§B) |
| Pre-origin span | [*D*₀, *O*₁): never a test fold; the only source of *H*, *c*min, *k*floor and the MDE simulation |
| Training window | Rolling 90 days; expanding within regime as sensitivity |
| Step and test fold | 7 days; refit weekly; an episode belongs to the fold containing its τ_k |
| Purge | A training episode requires τ_k + *H* ≤ origin |
| Normalisation | Every statistic — scaling, calibration, baserate — from the training window only, frozen for the fold |
| Learned components | Each registers `fit_data_max_published_at` and `pretrain_cutoff`; the harness refuses any fold whose origin precedes either. Retrospective topic assignment stays lexical |
| Cut-offs | Registered: the 2020-01-01 regime boundary (*proposed*, from the attention-acceleration evidence; applies only if history reaches it); every channel-list version change; every channel entry or exit. No training window spans a cut-off, and results are reported per regime |
| Live-start straddle | Episodes whose 28-day baseline straddles live-collection start are excluded from both evaluations: live rows survive deletion and retrieved rows do not, so the boundary carries a level step of roughly (1 − survival)/survival (*calculated*) that alone can satisfy *m* = 2 |
| Prohibited | Random or k-fold splitting; retrospective changepoint methods as labels or features; vocabulary revised after *t* |

**No retrospective lockbox.** Positives are scarce, and splitting them into two
underpowered evaluations is worse than one adequate evaluation. This holds under
one load-bearing condition: the timing-only specification is fixed in registration
v1 *before* counting, so every fold is out-of-sample for it. Any model specified
after Phase 2 results are seen is confirmed only on data accruing after its
specification is frozen (§A.9, §B Phase 5).

### A.6 How many positives are enough

Hanley–McNeil standard error of an absolute AUC (*calculated*):

| Per class | SE at AUC 0.70 | SE at AUC 0.75 | 95% half-width |
|---|---|---|---|
| 30 | — | 0.063 | ±0.12 |
| 50 | 0.052 | — | ±0.10 |
| 100 | 0.037 | 0.034 | ±0.07 |

- ***K*min = 100 positives and 100 negatives**, pooled across the test folds of the
  primary cell.
- **A second floor on independent units:** at least 20 distinct test weeks
  containing a positive. The Hanley–McNeil figures assume independent episodes,
  while the inference unit is the bootstrap block; one year of history gives
  247 test days ≈ 17 two-week blocks (*calculated*), so an episode count alone can
  overstate the evidence.
- **50 per class is the reporting floor**; below it, counts only, no AUC. Slices
  with fewer than 20 positives report counts only, labelled indicative.
- **Minimum detectable effect.** A minimum detectable Brier skill is registered,
  obtained by simulation on the pre-origin span. A Phase 2 null is reported as "not
  detectable at MDE = *x*", never as evidence that the effect is absent — the
  margin over baserate is expected to be small (*verified*: the best operational
  system beats a baserate model only slightly).

These figures bound an absolute AUC. The primary endpoint is a paired difference on
the same episodes and sheds shared variance; its interval comes from the bootstrap,
not from this table. Precision at alert volume is binomial: at 100 alerts and
precision 0.5, SE = 0.05 (*calculated*).

### A.7 Metrics

| Metric | Population | Reported with |
|---|---|---|
| AUC, accuracy | Episodes reaching *k*, excluding detected-at-crossing | Measured positive share; overshoot strata |
| **Precision and recall at alert volume** | A score threshold calibrated on the training window to admit a target fraction *A* ∈ {10%, 25%, 50%} of the eligible-episode rate measured on the pre-origin span, applied online | Realised alerts per week beside target; stream base rate; false alerts per week |
| Lead time | τ_k to the 2*k* tick, and to episode peak | Full distribution; detected-at-crossing count separately |
| Calibration | Brier score; Brier skill against baserate; reliability curve (≤ 10 bins) | Calibration fitted in training only |
| Breakdown | Topic, fold, regime, provenance, raw versus cleaned, channel type, planned versus unplanned | Slice positive counts |

Alert targets are fractions of the eligible rate rather than absolute alerts per
day: at the pass floor, eligible episodes arrive at about 0.81 per day
(*calculated*), so absolute targets of one, three or ten per day would admit every
episode and the metric would degenerate into the positive share. Top-*N*-per-period
alerting is not used, since ranking a period requires knowing its end.

**Single primary endpoint:** Brier skill score of timing-only against baserate,
pooled over test folds at the primary cell. Pass: 95% interval excludes 0.
Intervals: moving-block bootstrap over whole weeks (B = 2,000; block ≥ 2 weeks and
≥ *H*), paired for differences. Resampling whole weeks preserves within-week
dependence between topics responding to the same event; dependence across block
edges is a declared residual limitation. No single accuracy figure is given to
clients.

### A.8 Survivorship and reconstruction cost

1. Live collection starts on day one and never stops; it is the control.
2. **Complete strata, not scattered videos.** A registered random sample of
   *channel × week* strata is re-retrieved in full at 7, 30 and 90 days, from a
   reserved quota share, so that series and episodes can be rebuilt within a
   stratum. A sample of individual videos cannot rebuild a topic series.
3. Survival runs write to their own table and are excluded from the series builder
   — the one place where visibility reads provenance. Without this the instrument
   would inject a volume step into the very strata it measures.
4. Both directions are reported. **Survival** = live ids still returned ÷ live ids.
   **Coverage** = retrieved ids never seen live ÷ retrieved ids, which is also the
   empirical check on the replay rule.
5. **Both are upper bounds, and the direction is printed.** Items removed before
   the first live read never enter the denominator; and under a non-increasing
   deletion hazard the 90-day rate is an upper bound for every older period.
   Reconstructed periods therefore print "survival at the longest measured lag, an
   upper bound for older material". No extrapolation, no reweighting. The report
   refuses to render a reconstructed figure without it.
6. Stratified by topic, channel, channel type, and by the episode's **live label**
   (positive, negative, none) — the case in which deletion is least likely to be
   independent of the signal.
7. **Label flips are measured, not assumed away.** For live-era episodes, labels are
   built twice — strict live, and rebuilt from the 90-day re-retrieval under the
   replay rule — and the 2 × 2 agreement matrix is reported per cell.
8. **Reconstruction cost.** Within the sampled strata, the strict-mode live series
   is compared with the rebuilt series: count ratio and onset shift per topic.
   Metric-level cost is measured by prospective confirmation (Phase 5).

### A.9 Pre-registration

- **Pilot registration** (`config/pilot.yaml`), locked before any pilot collection:
  sample, strata, schedule, quota ceiling, span and permitted adaptations. Pilot
  data are excluded from confirmatory test folds.
- **Registration v1** (`config/preregistration.yaml`), locked after the pilot and
  before confirmatory retrieval:
  every definition in §A.2–A.8; the collection policy *P* of §0.3; the grid, primary
  cell and fallback; the timing-only specification; *K*min and the week floor;
  *D*₀ and *O*₁; the cut-offs; alert targets; integrity windows, thresholds and
  caps; event-matching rules; the completeness ratio; and the hashes of the frozen
  taxonomy and channel list.
- **Measured addendum** (`config/preregistration.measured.yaml`), locked before
  counting: λ, *c*min, *k*floor, the half-life and hence *H*, and the MDE — each
  computed by its registered rule from label-free data. **The lock is refused until
  the pre-origin span has been retrieved in full**, so that the addendum is never
  fitted on a span that later becomes a test fold.
- **Completeness.** Client-side exhaustion is unverifiable, so each retrieved video
  compares Σ(1 + reply total) against its own comment counter (one `videos.list`
  call per 50 videos, QA only, never a feature) and is censored below the
  registered ratio.
- SHA-256 of both files is committed in a lock file; counting and evaluation refuse
  to run on a mismatch and stamp the hash into every output. An append-only run
  register records every run and its date.
- **No silent relaxation.** If neither primary nor fallback cell reaches *K*min, the
  finding is "not backtestable on current history", with the forward accrual time
  at the observed live episode rate. A later registration version may change
  definitions; it is labelled post hoc, and v1 results remain the reported primary
  finding.

### A.10 Ground-truth event log

| Aspect | Rule |
|---|---|
| Role | T2, T3, and labelling alerts as calendar or forecast. **Never** a T1 label: T1 labels are intrinsic to the series |
| Candidates | Raw event-archive export and mentions (translated stream from 2015-02-19), and forward, feed items. Ranked **only on mentions timed within 24 h of the event**: later coverage accumulates precisely for the events that also produced comment surges, which would inflate T3 |
| Independence | No candidate generator reads video-platform data. **Curation runs during Phase 1 retrieval, before any series is built**, and the log is frozen and hashed before T2 or T3 run. The run register records the curation date against the first series build |
| Selection for T3 | Mechanical: a seeded, score-stratified draw from the approved pool. Not a human choice of memorable events |
| Curation | Every row enters by human approval against a rubric fixed in advance; archive fields are re-entered, not trusted (*measured* misattributions in sampled rows). Rejection reasons come from a closed factual list — wrong date, wrong geography, not domestic, duplicate — with no salience judgement |
| Consistency | Single curator: blind re-curation of a subset after at least one week, reported as intra-curator agreement |
| Known bias | Before feed collection, candidates come only from the foreign-dominated slice; domestic events without foreign coverage are under-represented. Log recall is reported per period |
| Matching | Fixed EMBERS rules: lead time > 0; dates within seven days; maximum-weight bipartite matching, each warning to at most one event |

### A.11 Event-impact measurement (T2)

For a logged event dated *d*ₑ on topic *i*:

- **Counterfactual baseline:** median and MAD over the 28 days ending *d*ₑ − 1,
  excluding days within 14 days of another logged event **on the same topic**. An
  all-topic exclusion would leave no baseline days at the planning figure of about
  ten events per month.
- **Displacement:** cumulative net excess over [*d*ₑ, *d*ₑ + 14 d].
- **Peak lag**, **duration** (until volume stays within baseline + 2 MAD for 24 h),
  **half-life** (peak to half of peak excess rate).
- **Placebo null:** the same statistics at up to 200 dates of the same topic and
  weekday with no logged event within ±14 days. "Distinguishable" requires
  exceeding the 95th percentile; **the realised placebo count is printed beside
  every percentile**, since one year of depth yields at most 52 such dates
  (*calculated*) and the percentile then rests on a handful of order statistics.
- Planned and unplanned events reported separately; reconstructed flag and survival
  rate on every figure; `media_attention` impact only for events after feed
  collection began.

### A.12 End-to-end known-event check (T3)

From the frozen log, **N ≥ 20** dated events within retrieval depth, drawn by the
mechanical rule of §A.10. A hit is an onset on the event's topic within
[*d*ₑ − 1, *d*ₑ + 1] days, using the online rule on the as-of series. Criterion:
hit rate ≥ 0.8 (*proposed*) **and** a lower hit rate at placebo dates at
permutation *p* < 0.01. Both parts are required: a detector that fires constantly
passes the first alone. All events are reported, hits and misses; planned events
separately.

---

## B. Phase order

Each phase is an end-to-end vertical slice closing on a figure; a negative figure is
a feasibility result, not a failure. Phases may overlap in the calendar; the order
is the order of exit criteria. Annotation, curation and engineering hours compete
for one developer.

| Phase | Slice | Feasibility question | Exit criterion |
|---|---|---|---|
| **1. Count the positives** | Frozen config and registration → live collection under policy *P*, feed collection, pilot, retrieval → as-of reader → raw and cleaned `public_engagement` → episodes → positive count per cell | Does available history hold enough surges to evaluate conditional growth, and at what quota cost? (Q1 volume, Q3 cost) | (a) pilot locked before pilot collection; v1 locked before confirmatory retrieval; addendum locked only after the pre-origin span is complete. (b) λ from ≥ 7 days live; exact replay checked on complete recorded histories; real reconstruction discrepancies reported. (c) Counts of eligible, positive, negative, censored and detected-at-crossing episodes per cell and span. (d) 7-day survival and coverage on complete strata. (e) Stratified topic audit with recall estimate, passing its registered floor. (f) Quota units spent equal the ledger; threads per video *measured*; monthly cost from ledger and disk. **Pass:** primary or fallback cell ≥ *K*min per class **and** ≥ 20 test weeks with a positive. **Otherwise:** the registered finding of §A.9 |
| **2. Conditional growth against baselines** | Walk-forward harness → baserate, persistence, timing-only → the metrics of §A.7 | Does timing beat baserate on this platform and language, and is a multi-day horizon meaningful given the measured half-life? | Primary endpoint with interval, and every §A.7 metric by slice, flagged reconstructed with survival. A null is reported against the registered MDE. Skipped if Phase 1 did not pass; T1 then waits on live accrual |
| **3. Language-layer accuracy** | Training toolchain demonstrated on the target machine → annotation harness → gold standard → teacher → student → descriptive `tone` | Q2: is the tone signal accurate enough to report? | ROADMAP thresholds: sentiment ≥ 0.75, stance ≥ 0.65 macro-F1, each above its majority-class and random baselines; intra-annotator agreement on 100 items re-labelled after ≥ 1 week. Below threshold is a finding |
| **4. Event log, impact, end-to-end** | Curated log (frozen during Phase 1) → T3, then T2 | Do known events register in the series, and is displacement distinguishable from placebo? | T3 criterion of §A.12 on ≥ 20 events; T2 table with placebo counts, percentiles and survival rates |
| **5. Forward-only components and prospective confirmation** | Accumulated live data → `media_attention`, `divergence`; the frozen Phase 2 model on live data; 30- and 90-day survival | Do the forward-only components add evidence, and does the reconstructed figure survive prospectively? | Triggered by count, not calendar. The prospective set contains only episodes whose τ_k is later than the model-freeze timestamp — not merely later than live-collection start, which Phase 2 has already scored. Prospective endpoint beside the reconstructed one, both with intervals; the gap is reported as reconstruction bias. Q3 refreshed |

**Annotation starts in Phase 1, week 1.** Tone is decoupled from forecasting, so
Phase 3's gold standard depends on nothing in Phases 1–2, and its risk is the one
the ROADMAP risk table marks as high impact and to be measured early. The 100-item
re-label needs a week's gap in any case.

### Phase 1 in order

1. Write and lock the pilot registration; freeze pilot taxonomy and sample by rules
   written without reference to any event, and referencing no counter. **The surge
   definition exists before a single episode is counted.**
2. Start live collection under policy *P* and feed collection — the survivorship
   clock and the forward-only clock. Start annotation.
3. **Pilot** (label-free): retrieve the registered bounded span for the fixed
   stratified channel sample; measure
   threads per video and the eligible-episode rate; project the depth needed for
   about 4 × *K*min eligible episodes; set *D*₀ within the retrieval reservation and
   register it in main v1 before confirmatory retrieval. Pilot data are excluded
   from confirmatory test folds. Where the projection exceeds the reservation, *D*₀ is set to what
   the reservation buys and the shortfall is stated in the count report.
4. Enumerate upload playlists back to *D*₀ for every channel, then retrieve the
   **pre-origin span first**, exhausting every video published in
   [*D*₀ − *w*, *O*₁), where *w* is the measured comment-activity window. Censoring
   is decided by this calendar rule, never per video: whether a video can be paged
   to exhaustion otherwise depends on its eventual comment count, which is
   post-outcome, and positives would be selectively dropped.
5. Day ≥ 8 and pre-origin span complete: measure λ, compute and lock the addendum.
6. Retrieve forward from *O*₁; build raw and cleaned series; count per cell; run the
   confirmatory topic audit; report survival and coverage; write the count report.

**Quota reservations** (*calculated*; three inputs unmeasured — videos per
channel-day, threads per video, and the realised cost of policy *P*):

| Reservation | Units/day | Basis |
|---|---|---|
| Live collection under *P* | 6,000 | 600 new videos/day × 6 polls = 3,600, plus 240 discovery calls, plus paging for new threads at 100 per unit |
| Historical retrieval | 3,000 | Remainder after the reservations below |
| Survival strata | 500 | Re-retrieval of complete channel-week strata at three lags |
| Buffer | 500 | Retry and re-poll overrun |

Reservations are enforced in the ledger: **retrieval cannot spend the live
reservation.** The consequence is deliberate and must be stated plainly: at
3,000 units/day, and on the synthesis's own arithmetic of ≈ 661,000 units per
history-year at three pages per video, one year of history would take about
220 days of retrieval (*calculated*). Deep history is therefore not free, the pilot
sizes *D*₀ against what the reservation actually buys, and "not backtestable on
current history" is a live possibility that Phase 1 is designed to surface early
rather than late.

---

## C. Phase 1 file list

Package root `sentira/`; tests mirror it under `tests/`. Future collector fixtures
are sanitised recorded API and feed responses; the offline foundation uses original
synthetic fixtures. No test touches the network. This is the full Phase 1 map;
[CONTINUATION](CONTINUATION.md) lists the smaller implemented subset and actual test names.

| File | Responsibility | Named test (file :: function) |
|---|---|---|
| `core/document.py` | Frozen `Document`; `DocumentKind {UTTERANCE, PUBLICATION}`; `Provenance`; field-class declaration; no raw-identifier and no counter field | `core/test_document.py::test_document_has_no_raw_identifier_field`; `::test_document_has_no_cumulative_counter_field`; `::test_every_field_declares_exactly_one_class` |
| `core/identity.py` | HMAC-SHA256 over platform name and raw id, for author, comment and parent ids; key from environment; fails at start-up if absent | `core/test_identity.py::test_same_id_on_two_platforms_hashes_differently`; `::test_missing_key_fails_at_startup` |
| `config/schema.py` | Validated loading of channels, feeds, taxonomy, targets and registration; target types restricted to parties, state institutions and declared candidates; channel-selection rule references no counter | `config/test_schema.py::test_target_of_disallowed_type_rejected_at_load`; `::test_channel_selection_rule_references_no_counter`; `::test_shipped_config_files_validate` |
| `collectors/policy.py` | Registered collection policy *P*: discovery ticks, poll ages, page cap; replay time *R*(row) for retrieved rows | `collectors/test_policy.py::test_replay_matches_live_visibility_on_recorded_video` (planned; implemented offline as `::test_replay_matches_live_visibility_on_synthetic_complete_history`); `::test_row_beyond_page_cap_never_replay_visible`; `::test_row_after_last_poll_age_never_replay_visible` |
| `collectors/quota.py` | Persistent ledger debited before each call; separate reservations for live, retrieval and survival; clean stop before exhaustion | `collectors/test_quota.py::test_ledger_debited_before_call`; `::test_ledger_units_equal_calls_made`; `::test_exhaustion_stops_cleanly_and_persists_collected`; `::test_retrieval_cannot_spend_live_reservation` |
| `collectors/youtube.py` | `playlistItems` + `commentThreads` only (plus `videos.list` for the completeness counter, QA only); UC→UU derivation; live polling under *P* and retrieval mode; ids and authors hashed before any object is emitted; counters emitted as snapshots only | `collectors/test_youtube.py::test_only_permitted_endpoints_called`; `::test_uploads_playlist_id_derived_from_channel_id`; `::test_raw_author_id_absent_from_every_emitted_object`; `::test_raw_comment_id_absent_from_every_emitted_object`; `::test_video_below_completeness_ratio_marked_censored` |
| `collectors/feeds.py` | Poll news feeds as `PUBLICATION` (title, summary, `pubDate`; explicit UTF-8); byline and creator fields dropped; report window gaps. In Phase 1 because an unpolled feed window is permanently lost | `collectors/test_feeds.py::test_item_stored_as_publication_without_tone`; `::test_author_and_creator_fields_dropped`; `::test_gap_reported_when_window_rolled_past_last_seen` |
| `storage/schema.py` | Portable DDL: `documents`, `snapshots(doc_hash, observed_at, metric, value)`, `survival_probes`, `quota_ledger`, `runs` | `storage/test_schema.py::test_schema_has_no_raw_identifier_columns`; `::test_documents_table_has_no_counter_columns`; `::test_every_column_has_exactly_one_field_class` |
| `storage/repository.py` | Writes; `observed_at` from the injected storage clock; insert-once | `storage/test_repository.py::test_observed_at_cannot_be_supplied_by_caller`; `::test_first_observation_wins_on_reingest` |
| `storage/asof.py` | The single point-in-time reader of §0.2–0.3; replay visibility; reconstruction flag per *T*; strict mode | `storage/test_asof.py::test_row_invisible_unless_observed_by_T_or_replay_visible_by_T`; `::test_row_admitted_by_replay_is_flagged_reconstructed`; `::test_reconstructed_row_exposes_immutable_fields_only`; `::test_item_edited_after_T_contributes_to_no_topic_at_T`; `::test_snapshot_observed_after_T_never_read`; `::test_publication_visible_only_by_observed_at`; `::test_channel_added_after_v1_contributes_no_rows_before_added_at`; `::test_survival_probe_rows_invisible_to_series_builder`; `::test_strict_mode_admits_only_rows_observed_by_T` |
| (architecture) | Enforces the single read path | `test_architecture.py::test_only_storage_imports_database_driver` |
| `nlp/topics.py` | Single-label lexical assignment on as-of comment text against the frozen taxonomy, by the registered priority rule | `nlp/test_topics.py::test_uses_frozen_taxonomy_hash`; `::test_assignment_reads_only_as_of_text`; `::test_video_title_not_used_for_assignment`; `::test_single_label_priority_rule_deterministic` |
| `nlp/integrity.py` | As-of screens computed by the reader: near-duplicate text across author hashes within a registered window; per-author cap per topic-interval; co-commenting author sets across videos. Never a volume-burst screen | `nlp/test_integrity.py::test_flag_at_T_invariant_to_rows_invisible_at_T`; `::test_later_duplicate_wave_does_not_flag_earlier_copies`; `::test_cleaned_series_not_reduced_by_volume_alone`; `::test_cleaned_count_never_exceeds_raw` |
| `series/engagement.py` | Hourly `public_engagement`, raw and cleaned, through `as_of` only, with `share_reconstructed` and censored cells | `series/test_engagement.py::test_series_at_T_invariant_to_rows_invisible_at_T` (property-based: mutating or deleting any row invisible at *T* leaves the output unchanged); `::test_reconstructed_share_propagates` |
| `series/episodes.py` | Baseline, onset, net size, τ_k on the as-of series, labels, censoring, overshoot, detected-at-crossing, current-baseline end rule, excess half-life | `series/test_episodes.py::test_tk_is_first_tick_at_which_asof_series_reaches_k`; `::test_onset_invariant_to_rows_invisible_at_T`; `::test_detected_at_crossing_excluded_from_t1_population`; `::test_unresolved_horizon_is_censored_not_negative`; `::test_resolution_time_is_tk_plus_H_for_both_classes`; `::test_level_shift_does_not_extend_episode_past_max_duration`; `::test_half_life_recovered_on_synthetic_decay` |
| `backtest/registration.py` | Verifies the locks; computes the measured addendum from label-free data; run register | `backtest/test_registration.py::test_count_refuses_on_registration_hash_mismatch`; `::test_first_origin_is_registered_constant`; `::test_addendum_refused_until_preorigin_span_complete`; `::test_lambda_computed_from_live_rows_only`; `::test_integrity_parameters_registered` |
| `backtest/positives.py` | Counts per cell and span; fallback rule; week-floor check; writes the count report with provenance labels | `backtest/test_positives.py::test_counts_match_hand_labelled_fixture`; `::test_fallback_cell_chosen_by_registered_rule`; `::test_week_floor_enforced`; `::test_report_refuses_reconstructed_figure_without_survival_rate`; `::test_reconstructed_raw_series_labelled_platform_filtered` |
| `backtest/survival.py` | Re-retrieval of complete channel-week strata at fixed lags into `survival_probes`; survival and coverage with their bounds | `backtest/test_survival.py::test_survival_denominator_is_live_ids`; `::test_coverage_counts_retrieved_ids_never_seen_live`; `::test_probe_rows_never_enter_documents`; `::test_no_extrapolation_beyond_longest_measured_lag` |
| `eval/topic_audit.py` | Seeded blind sample stratified across positive, negative and non-episode intervals; precision and recall with Wilson intervals; items carry no timestamp or episode id | `eval/test_topic_audit.py::test_sample_is_seeded_and_stratified`; `::test_audit_items_carry_no_timestamp_or_episode_id`; `::test_development_audit_samples_pre_origin_span_only`; `::test_wilson_interval_known_values` |
| `cli.py` | `collect-live`, `pilot`, `retrieve`, `survive`, `register-measured`, `count`, `audit`, `cost` | `test_cli.py::test_collect_exits_zero_on_quota_exhaustion`; `test_phase1_e2e.py::test_recorded_fixtures_to_positive_count_end_to_end` |

Configuration (data, not code): `config/channels.yaml` (frozen list, channel type,
`added_at`, selection rule), `config/feeds.yaml`, `config/topics.yaml` (standing
institutional topics, `frozen_at`), `config/preregistration.yaml`,
`config/preregistration.measured.yaml`, `config/preregistration.lock` — all covered
by `::test_shipped_config_files_validate` and the registration tests. No target
file ships in Phase 1; the restriction is in force in the loader from the first
commit. Support only: `pyproject.toml`, `.env.example`, `tests/conftest.py` (fixed
clock, temporary database), `tests/fixtures/`.

**Section 1 guarantees → tests**

| Guarantee | Test |
|---|---|
| Quota ledger debited before the call | `test_quota.py::test_ledger_debited_before_call`, `::test_ledger_units_equal_calls_made` |
| Clean stop on exhaustion, data persisted | `test_quota.py::test_exhaustion_stops_cleanly_and_persists_collected`, `test_cli.py::test_collect_exits_zero_on_quota_exhaustion` |
| No raw-identifier column or field | `test_schema.py::test_schema_has_no_raw_identifier_columns`, `test_document.py::test_document_has_no_raw_identifier_field`, `test_youtube.py::test_raw_comment_id_absent_from_every_emitted_object` |
| Hashing at the collector boundary, platform in the input | `test_youtube.py::test_raw_author_id_absent_from_every_emitted_object`, `test_identity.py::test_same_id_on_two_platforms_hashes_differently` |
| Counters only in snapshots | `test_document.py::test_document_has_no_cumulative_counter_field`, `test_schema.py::test_documents_table_has_no_counter_columns` |
| Point-in-time read rule, as amended | `test_engagement.py::test_series_at_T_invariant_to_rows_invisible_at_T`, `test_episodes.py::test_onset_invariant_to_rows_invisible_at_T`, the nine `test_asof.py` cases, `test_repository.py` (two), `test_architecture.py::test_only_storage_imports_database_driver` |
| Replay fidelity | `test_policy.py::test_replay_matches_live_visibility_on_recorded_video` (planned); implemented offline as `collectors/test_policy.py::test_replay_matches_live_visibility_on_synthetic_complete_history` |
| Config target-type restriction | `test_schema.py::test_target_of_disallowed_type_rejected_at_load` |
| No search endpoint | `test_youtube.py::test_only_permitted_endpoints_called`; implemented offline as `collectors/test_quota.py::test_unregistered_endpoint_refused_before_any_debit` |
| Pre-registration binding | `test_registration.py::test_count_refuses_on_registration_hash_mismatch` |

Nineteen modules. Deliberately absent: `forecast/`, `report/`, sentiment, stance,
the event-archive retriever, walk-forward code, and any `media_attention` or
`divergence` series. Each enters with the phase that measures it.

---

## D. Open questions

1. **Threads per video** on the curated list, and **videos per channel-day** — both
   set retrieval cost and attainable depth, and both are currently calculated
   assumptions. First measurements of the Phase 1 pilot.
2. **Realised cost of policy *P***. The 6,000-unit live reservation is arithmetic
   over assumed volumes; the schedule is re-costed against the pilot before v1 is
   locked.
3. **Whether a comment-id lookup returns the author.** One authenticated
   `comments.list` call settles it (1 unit). Hashing is adopted regardless; the
   answer determines whether the exposure was real and belongs in the compliance
   record.
4. **Retrieval completeness and order.** Comment threads are ordered by time
   (*verified*, API documentation); direction and completeness for large old videos
   are not documented and are confirmed against a live-observed video.
5. **Reliability of `updated_at`.** The field is documented (*verified*); whether it
   changes on every edit is not. If not, comment text falls under the unversioned
   class and reconstructed topic assignment is withdrawn — which would end the
   retrospective backtest.
6. **Upload-playlist ceiling.** A limit of 20,000 items is reported but unverified;
   it would cap reachable history for high-volume channels at roughly 333 days at
   60 uploads per day (*calculated*).
7. **Acceptable alert volume** for an institutional client. No figure exists for
   this domain; *A* stays a grid.
8. **Taxonomy authorship and size.** The frozen vocabulary determines the positives;
   who writes it, and against which rule, is not yet fixed.
9. **Translated-stream archive for 2015–2017** — one request per year settles it;
   relevant to event-log candidates only.

---

## E. Consequences for the other documents

Approval of this section changed four published documents, so that the repository
does not contradict itself: the point-in-time rule and the survivorship sentence in
[ROADMAP](ROADMAP.md) and the [README](../README.md); leakage controls 1 and 4, the
surge definition and the first quantity to measure in
[FORECASTING](FORECASTING.md); and, in [FEASIBILITY](FEASIBILITY.md), the quota
arithmetic, which the registered polling policy supersedes, together with the
forward-only status of feed-derived series and the role of the event archive.
