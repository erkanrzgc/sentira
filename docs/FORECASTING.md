# Forecasting: what the evidence supports

This record sets the limits within which Sentira's foresight claims are made.
Entries marked *verified* were extracted from the primary source — the paper itself
or official documentation. Entries drawn only from search summaries are excluded
from this record and are not used in client material.

---

## Summary

The claim "a subject that is quiet now will surge within days" has **no published
accuracy figure**. Every figure available concerns a conditional task: content that
has already reached a threshold, or warnings generated from an external event
stream. Four independent lines of evidence converge on the same limit:

- the best cascade models explain less than half of the variance in final size;
- the best-funded operational early-warning system improves on a naive baserate
  model by a small margin;
- automated event coding was below 50% accuracy before modern NLP;
- attention windows are measured in hours, not days.

What is supported is narrower: **conditional growth estimation** — ranking subjects
already in motion by their calibrated probability of growing further. Sentira
claims that, and only that.

---

## Evidence

| Finding | Source | Status | Consequence |
|---|---|---|---|
| Conditional doubling task — observe a cascade at size *k* = 5, predict whether it reaches 2*k*: accuracy 0.795, AUC 0.877 | Cheng et al. 2014 | verified | The most optimistic reference point. Classes are balanced by design (random guessing scores 50%); in a live stream the positive rate is of the order of 1% |
| Temporal features outperform every other single feature set and fall within 0.025 of the full model; best single feature (reshare rate in the second half of the window) scores 0.73 | Cheng et al. 2014 | verified | Invest in timing features before content features |
| Text sentiment features (positive, negative, social categories) perform at chance: accuracy 0.49–0.52 | Cheng et al. 2014 | verified | Tone is a separate product, not a forecasting feature |
| Cascades originating from pages exceed 0.80 accuracy; those from individual users fall below 0.70 | Cheng et al. 2014 | verified | Agenda originating from institutional and media accounts is more predictable |
| No sweet spot: performance rises roughly linearly in *k*, from 0.724 (*k* = 5) to 0.808 (*k* = 100) | Cheng et al. 2014 | verified | The earlier the warning, the weaker it is |
| The best models explain less than half of the variance in cascade size; even with unlimited data, performance is bounded well below deterministic accuracy | Martin et al. 2016 | verified | The ceiling is a property of the system, not of the model |
| EMBERS: quality score 3.11, mean lead time 8.8 days, precision 0.69, recall 0.82 | Ramakrishnan et al. 2014 | verified | A multi-day horizon is operationally possible — subject to the next row |
| EMBERS improves on baserate methods by approximately +0.4 quality points (+1.0 under strict location matching) | Ramakrishnan et al. 2014 | verified | Every figure must be reported against a baserate model |
| The highest-quality, longest-lead EMBERS warnings came from planned-event pages | Ramakrishnan et al. 2014 | verified | Much early warning is calendar reading and must be labelled as such |
| Precision by country and month ranges 0.45–1.0; recall 0.59–1.0 | Ramakrishnan et al. 2014 | verified | A single average misleads; report by topic and period |
| Automated event coding: an older system 42–45% accurate, a newer NLP system 74–86%, against human coders over 3,000 events | Ward et al. 2013 | verified | Automated event extraction is the weakest link in the chain |
| Residence time in the top-50 hashtags fell from 17.5 hours (2013) to 11.9 hours (2016) | Lorenz-Spreen et al. 2019 | verified | Attention decays within hours; this is in tension with multi-day warning horizons |
| Prophet infers changepoints only within the first 80% of a series, retrospectively; no online mode is documented | Prophet documentation | verified | Using its changepoints as labels or features leaks the future into a backtest |

## Negative findings

1. **No published accuracy exists for detecting subjects that are not yet
   visible.**
2. **The ceiling is real and low.** It is a property of social systems, not a
   shortfall of current models.
3. **Sentiment performs at chance for growth prediction.**
4. **The best operational system is only slightly ahead of a naive baserate.**
5. **Long lead times come from calendars, not prediction.**
6. **No accuracy figure exists for the target language or for video-platform
   commentary.** All evidence comes from other platforms and regions;
   transferability is unmeasured.
7. **Readily found high figures are usually unsound.** Values such as "94% trend
   prediction accuracy" circulate without a task definition or base rate, and
   vendor claims should be read accordingly.

---

## Leakage controls

Enforced in code, not left to convention:

1. **Cumulative counters are contaminated.** In historical retrieval, a comment's
   publication time is faithful to the past, but view, comment and like counts are
   today's cumulative values. Point-in-time state is re-derived only from items with
   `published_at ≤ t`, or from the observation snapshot table.
2. **No retrospective changepoint methods** (such as Prophet) as labels or
   features. Online methods, such as Bayesian online changepoint detection, are
   preferred; their calibration on this data is not yet measured.
3. **Vocabulary frozen at *t*.** Choosing keywords after seeing what surged is
   hindsight selection in feature space.
4. **Walk-forward only.** Random k-fold splitting is prohibited; the training window
   always ends before the prediction time, and normalisation statistics come from
   the training window alone.
5. **Matching rules fixed before evaluation**, following the EMBERS scheme: lead
   time greater than zero; predicted and actual dates within seven days; each
   warning matched to at most one event by maximum-weight bipartite matching.
   Relaxing rules after seeing results is fabrication.
6. **A baserate model always runs** — extending the rate of the preceding three
   months. The EMBERS margin shows how strong this competitor is.

## Defining a surge

| # | Paradigm | Definition | Strength | Weakness |
|---|---|---|---|---|
| 1 | **Relative, self-calibrating** (Cheng) | Among subjects that reached *k*, the median final size is *f*(*k*); a surge is exceeding it, equivalently reaching 2*k* | Balanced by design; no arbitrary threshold; no external labels; predictability measurable as a function of *k* | Conditional — defined only for subjects already in motion |
| 2 | **External ground truth** (EMBERS) | A human-curated, news-based event record, matched to warnings by rule | Meaningful to a client; operational | No such record exists for the operating context; building one is continuous manual work |
| 3 | **Statistical burst state** (Kleinberg) | A two-state automaton; a jump in intensity is a burst | Automatic; yields hierarchical structure | Assumes Poisson arrivals; no model of automated or coordinated accounts; blind to low-visibility subjects |

**Adopted: paradigm 1 as primary, paradigm 3 as supporting.** The base rate is
always reported separately — the 50% in paradigm 1 is a design property, and in the
stream a client actually sees, the share of surging subjects is of the order of one
percent. What is reported is therefore not balanced accuracy but **precision at the
alert volume the client actually receives**, together with the cost of alert
fatigue.

---

## Consequences for the product

- **Early warning** is restricted to conditional growth: ranking subjects already
  in motion.
- **Event impact** is measured retrospectively — how far a known event displaced
  attention and for how long. The only direct evidence bearing on it is the
  shortening of attention lifetimes.
- **Forecasting reaction to a hypothetical future event** has no supporting
  evidence in this record and is not offered.
- **No single accuracy figure is given.** Following the EMBERS approach, date,
  subject and magnitude accuracy are reported separately, with variance broken down
  by topic and period.
- **Planned events and forecasts are separated.** A calendar of announced events is
  carried as its own stream and is not presented as prediction.
- **The first quantity to measure** is the half-life of attention in
  video-platform commentary; it determines whether a multi-day horizon is
  meaningful at all.

## Open questions

1. Is there any published surge-prediction accuracy for the target language?
2. Is there published cascade or burst prediction on video-platform comments?
3. How do online changepoint methods compare with retrospective ones on real data?
   No benchmark with figures was located.
4. What alert precision do institutional clients accept? Clinical literature
   discusses this; no figure exists for this domain.
5. How far does coordinated activity degrade burst detection?

---

## References

- Cheng, J., Adamic, L., Dow, P. A., Kleinberg, J., & Leskovec, J. (2014). Can
  cascades be predicted? *Proceedings of WWW '14*.
- Martin, T., Hofman, J. M., Sharma, A., Anderson, A., & Watts, D. J. (2016).
  Exploring limits to prediction in complex social systems. *Proceedings of
  WWW '16*.
- Ramakrishnan, N., et al. (2014). 'Beating the news' with EMBERS: Forecasting civil
  unrest using open source indicators. *Proceedings of KDD '14*. arXiv:1402.7035.
- Ward, M. D., et al. (2013). Comparing GDELT and ICEWS event data.
- Lorenz-Spreen, P., et al. (2019). Accelerating dynamics of collective attention.
  *Nature Communications*, 10, 1759.
- Prophet documentation, "Trend changepoints".
- Adams, R. P., & MacKay, D. J. C. (2007). Bayesian online changepoint detection.
  arXiv:0710.3742.
