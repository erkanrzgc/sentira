# Roadmap

This document records the purpose of the current stage, the state of the design,
the decisions carried forward, and the criteria by which the work will be judged.

---

## Purpose of the current stage

The current stage is feasibility, not production. It seeks three figures sufficient
for a decision:

1. How much data is lawfully available per month?
2. How accurate is the signal derived from it?
3. What does it cost per month?

The work is organised so that answering these questions also leaves a skeleton able
to grow into a production system. Current answers are in
[FEASIBILITY.md](FEASIBILITY.md).

## Sequencing principle

**Evidence first.** The output of feasibility is not whether the system runs but
how accurate it is; without that figure the work reduces to a demonstration. The
annotation and evaluation harness is therefore built before the language layers it
measures, and every later layer is measured against it. Each phase leaves an
end-to-end vertical slice.

---

## Design status

| Section | Scope | Status |
|---|---|---|
| 1 | Module layout, point-in-time correctness, survivorship | Approved |
| 2 | Document model and source fusion | Approved |
| 3 | Backtest protocol, phase order, first implementation files | Approved — [BACKTEST.md](BACKTEST.md) |

The [implementation amendment](IMPLEMENTATION_START.md) bounds the current code
to synthetic data and strict observation-time reads. [SOURCE_USE](SOURCE_USE.md)
records live-data blockers; [CONTINUATION](CONTINUATION.md) records tested coverage.

### Section 1 — Module layout and temporal correctness

- Modules: `core/ config/ collectors/ storage/ nlp/ series/ forecast/ backtest/
  report/ eval/`, each with a single responsibility (see the
  [README](../README.md#architecture)).
- Every document carries `published_at` and `observed_at`. Cumulative counters are
  never stored on the document; they are recorded in
  `snapshots(doc_id, observed_at, metric, value)`, and are read only from snapshots
  observed at or before *T*. An item retrieved after *T* contributes only its
  immutable fields — identifiers, publication time, hashed author, and text not
  edited after *T* — and only where the registered collection policy would have
  retrieved it by *T*; every value so derived is flagged as reconstructed. A single
  strict read path is implemented for synthetic observations. Historical visibility
  remains conditional on evidence, as qualified by the implementation amendment
  ([BACKTEST.md](BACKTEST.md#0-the-point-in-time-rule-reconciled-with-historical-retrieval)).
- Survivorship: continuous collection runs alongside historical retrieval as a
  control, and every retrospective result is reported together with the survival
  rate at the longest measured lag, which is an upper bound for older material.
- Tone is decoupled from forecasting. In the published literature, sentiment
  features scored at chance in the cited cascade study; transfer is unmeasured; see
  [FORECASTING.md](FORECASTING.md).

### Section 2 — Document model and source fusion

- One `Document` envelope, two kinds:
  - `UTTERANCE` — authored commentary. Has a hashed author; carries tone.
  - `PUBLICATION` — a news item. An agenda event; carries no tone.

  Sentiment and stance run on utterances only.
- Fusion does not blend sources into a single index. A topic series is
  `{media_attention, public_engagement, tone, divergence}`, and the divergence
  between media attention and public engagement is itself a reported quantity.
- Each series declares its own historical depth.
- Weighting among sources of the same kind is deferred until a second such source
  exists.
- Raw and integrity-cleaned series are produced together; the difference between
  them is a finding in its own right.

### Section 3 — Backtest protocol, phase order, first implementation files

Stated in full in [BACKTEST.md](BACKTEST.md); in summary:

- **Point in time.** Historical retrieval is admitted by a *replay rule*: a
  retrieved row is visible at *T* only where the registered collection policy would
  have retrieved it by *T*. Counters are never read from a retrieved row.
- **Candidate retrospective component.** Only the comment-count component of `public_engagement`,
  flagged reconstructed and printed with its survival rate. Survivor-only history
  does not establish confirmatory visibility. Views, likes,
  `media_attention` and `divergence` are forward-only from the first day of
  collection, which is why collection starts before any series is built.
- **Surge definition.** Net excess over a trailing baseline frozen at onset;
  conditional doubling within a horizon fixed by the measured half-life. The
  conditioning instant is the poll at which the system would have *seen* the
  threshold crossed, not the moment the comment was posted; episodes already
  doubled when first seen admit no forecast and are excluded and reported.
- **Registered before counting.** Every definition, threshold and matching rule is
  locked and hashed before confirmatory retrieval begins, after a separately
  registered pilot; the evaluation refuses to run against
  a modified registration.
- **Phase order.** 1 count the positives · 2 conditional growth against baselines ·
  3 language-layer accuracy · 4 event log, impact and end-to-end · 5 forward-only
  components and prospective confirmation. Annotation begins in phase 1.
- **The first question is whether the evaluation is possible at all.** A polling
  policy adequate to serve as a control consumes most of the daily quota, so
  historical depth is expensive. Phase 1 exists to establish, in weeks, whether
  available history holds enough surges; where it does not, the registered finding
  is that conditional growth can only be evaluated on data collected forward.

---

## Decisions carried forward

**Quota-aware collection.** Video discovery enumerates the upload playlists of a
curated channel list (1 unit per call) rather than using search, which remains outside the registered endpoint set.
The current official quota table assigns search a separate daily bucket; see
[SOURCE_USE](SOURCE_USE.md). The collector keeps a quota ledger that is debited *before* each call and
stops before exhaustion. Live collection, historical retrieval and survival checks
draw on separate reservations, and retrieval cannot spend the live reservation.
Arithmetic in [FEASIBILITY.md](FEASIBILITY.md#1-collection-volume-and-cost).

**Sentiment and stance are separate layers.** "The economy is a disaster" carries
negative sentiment, but its stance — toward whom — depends on context. The sentiment
layer produces polarity; the stance layer produces `{favour, against, unrelated}`
separately for each configured target. No ready-made political stance model exists
for the target language.

**Local inference only.** The reason is legal rather than financial. Sending
political opinion to a hosted inference API is a cross-border transfer of
special-category personal data. Local inference removes that item. It does not
establish a lawful basis for processing; the principal mitigations are the
aggregate-only design and identity hashing, not locality. Recorded as an open item
in [CONCEPT.md](CONCEPT.md#5-open-items).

**Distillation.** A local large language model labels; a ~110M-parameter encoder
serves. The delivered system therefore runs on modest hardware without a GPU
cluster. See [MODELS.md](MODELS.md).

**Integrity screening is mandatory.** Coordinated activity is real in political
discourse and distorts the signal. The integrity layer flags suspect volume through
near-duplicate text and repeated-author/co-commenting patterns in registered
windows. Topic volume alone must never trigger filtering.

**Historical implementation claims, not evidence for this checkout:**

The following behaviours were reported for an earlier implementation. Only the
offline subset listed in CONTINUATION is tested in this repository:

- The quota ledger is debited before the call, not after; a test asserts that
  ledger units equal the number of API calls actually made.
- Author identity is hashed at the collector boundary, not in storage; the
  `Document` type has no raw-identifier field, enforced in test.
- The schema contains no raw-identifier columns such as `username` or
  `profile_url`; a test scans the schema to confirm this.
- On quota exhaustion the collector stops cleanly: no exception escapes, and data
  collected so far is persisted.

---

## Validation criteria

- **Accuracy.** Macro-F1 for sentiment and stance, each reported beside a
  majority-class and a random baseline. Acceptance: sentiment ≥ 0.75 and stance
  ≥ 0.65, each clearly above its majority-class baseline. A result below threshold
  is a finding of the feasibility study and is reported as such.
- **Annotation consistency.** Intra-annotator agreement on a 100-item subset
  re-labelled blind after at least one week, named as intra-annotator.
- **End-to-end.** On at least 20 dated events drawn mechanically from a frozen,
  independently curated event log, an episode opens within one day of the event
  date for at least 80%, and the rate at placebo dates is lower at *p* < 0.01.
- **Forecasting.** Walk-forward evaluation against a baserate model under matching
  rules fixed in advance; see [FORECASTING.md](FORECASTING.md#leakage-controls).
  Evaluated only once the available history holds at least 100 positive and 100
  negative episodes across at least 20 distinct test weeks; primary endpoint Brier
  skill against the baserate, reported against a registered minimum detectable
  effect.
- **Engineering.** Tests green; at least 80% coverage on critical paths.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Quota increase refused | Medium | Actual polling, refresh and survival cost remains to be measured |
| Stance accuracy in the target language is low | High | Measured early against the gold standard; scope adjusted, or the work not taken on |
| Coordinated activity distorts the signal | High | Integrity layer; raw and cleaned series side by side |
| Client requests person-level output | Medium | Excluded in writing in advance; justified by the aggregate-only design |
| Metered platform pricing changes | Low | Metered sources sit behind a flag and are optional |

## Outside the current stage

Metered platform integration (skeleton behind a flag, disabled), a dashboard (a
separate piece of work once report value is demonstrated), closed platforms, and any
form of person-level output.
