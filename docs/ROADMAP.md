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
| 3 | Backtest design, phase order, first implementation files | **Pending** |

### Section 1 — Module layout and temporal correctness

- Modules: `core/ config/ collectors/ storage/ nlp/ series/ forecast/ backtest/
  report/ eval/`, each with a single responsibility (see the
  [README](../README.md#architecture)).
- Every document carries `published_at` and `observed_at`. Cumulative counters are
  never stored on the document; they are recorded in
  `snapshots(doc_id, observed_at, metric, value)`. A feature computed for time *T*
  reads only rows observed at or before *T*, and a test enforces this.
- Survivorship: continuous collection runs alongside historical retrieval as a
  control, and every retrospective result reports its uncorrected survival rate.
- Tone is decoupled from forecasting. In the published literature, sentiment
  features score at chance for growth prediction; see
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

### Section 3 — Pending

Backtest protocol, phase order and the first implementation files are not yet
fixed. The phase order is deliberately not stated here: it follows from the
backtest design and would otherwise be committed to prematurely.

---

## Decisions carried forward

**Quota-aware collection.** Video discovery enumerates the upload playlists of a
curated channel list (1 unit per call) rather than using search (100 units per
call). The collector keeps a quota ledger that is debited *before* each call and
stops before exhaustion. Arithmetic in [FEASIBILITY.md](FEASIBILITY.md#1-collection-volume-and-cost).

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
near-duplicate text, bursts within time windows and repeated-author signals.

**Behaviour verified in an earlier implementation, to be preserved:**

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
- **End-to-end.** A report generated over a known, dated event: the step in the
  series must coincide with the event date.
- **Forecasting.** Walk-forward evaluation against a baserate model under matching
  rules fixed in advance; see [FORECASTING.md](FORECASTING.md#leakage-controls).
- **Engineering.** Tests green; at least 80% coverage on critical paths.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Quota increase refused | Medium | The design already fits within the free daily quota |
| Stance accuracy in the target language is low | High | Measured early against the gold standard; scope adjusted, or the work not taken on |
| Coordinated activity distorts the signal | High | Integrity layer; raw and cleaned series side by side |
| Client requests person-level output | Medium | Excluded in writing in advance; justified by the aggregate-only design |
| Metered platform pricing changes | Low | Metered sources sit behind a flag and are optional |

## Outside the current stage

Metered platform integration (skeleton behind a flag, disabled), a dashboard (a
separate piece of work once report value is demonstrated), closed platforms, and any
form of person-level output.
