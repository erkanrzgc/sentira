# Topic taxonomy, lexical assignment and the topic audit

Status: authorised by the operator on 2 October 2026. It implements the frozen
taxonomy, single-label lexical assignment and the topic audit of
[BACKTEST](../../BACKTEST.md) §A.2, §0.4 and §C for synthetic text only. The
keywords in the repository are invented words; the real keyword lists are written
before the pilot.

## Operator decisions, 2 October 2026

| Question | Decision |
|---|---|
| Who writes the taxonomy | Claude drafts the topics, the operator approves them; the keyword lists follow before the pilot |
| A comment that matches several topics | The topic with the most distinct matching keywords wins; a tie goes to the topic registered first |
| Who labels the audit and agreement set | One annotator; 100 items are re-labelled blind after at least one week, and agreement is reported as intra-annotator Cohen's kappa |
| Topics | The eleven standing topics below, approved as drafted |

## Topics

Standing institutional subjects only, named without reference to any event. The
order is registered and breaks ties.

| Order | Identifier | Covers |
|---|---|---|
| 1 | `economy` | Prices, inflation, exchange rates, gold, stock markets, wages, taxes |
| 2 | `health` | Hospitals, the health system, medicines |
| 3 | `education` | Schools, universities, examinations |
| 4 | `justice` | Courts, the judiciary, legislation |
| 5 | `security` | Police, crime, terrorism |
| 6 | `foreign-policy` | Diplomacy and international relations |
| 7 | `environment-and-disasters` | Earthquakes, floods, climate, the environment |
| 8 | `local-services` | Municipal services, transport, water, housing |
| 9 | `energy` | Electricity, gas and fuel supply |
| 10 | `social-security` | Pensions, social assistance, employment |
| 11 | `elections` | Electoral processes, parties, campaigns |

Economy is a topic because the operator decided to measure discourse about the
economy, including markets and gold; market data themselves are deferred (ROADMAP,
"Operator decisions, 2 October 2026: markets and the economy").

## Taxonomy rules

| Rule | Behaviour |
|---|---|
| Keywords | A whole word, or a stem of at least four letters ending in `*`; letters only, written in normalised form |
| Ownership | A keyword belongs to one topic only |
| Normalisation | A registered case map folds characters before lower-casing, so language-specific case folding is data, not code |
| Freezing | `frozen_at` and the content digest; assignment refuses a taxonomy whose digest differs from the registered one |
| Counters | Unknown fields are refused, so no topic can be defined by a counter |

A lexical matcher sees surface forms. In a language that builds words with
suffixes, a whole-word keyword misses inflected forms and a short stem catches
unrelated words; stems of at least four letters are a compromise, and their
precision and recall are what the audit measures. Normalisation beyond case
folding is a later step.

## Assignment

`nlp/topics.py` assigns only utterances in an as-of read, so a comment edited after
*T* belongs to no topic at *T*, and publication text such as a video title is never
used. Each assignment records the taxonomy digest.

## Audit and agreement set

| Element | Design |
|---|---|
| Sample | Seeded, per stratum: positive-episode, negative-episode and non-episode intervals, crossed with assigned and unassigned comments as the strata the caller supplies |
| Span | A development audit draws only from before the first origin; a confirmatory audit only from after it |
| Blinding | Items carry an opaque identifier and the text; they are shuffled across strata; the key to documents, strata and assignments is kept apart |
| Size | About 100 items per stratum give a Wilson interval of roughly ±0.1 at a proportion of one half (*calculated*) |
| Metrics | Precision and recall per topic with Wilson score intervals, unweighted across strata |
| Floor | Recall is compared with a registered floor through the lower interval bound; the floor is registered with the pilot |
| Agreement | Cohen's kappa between the first labelling and the blind re-labelling of 100 items after at least a week |

## Acceptance tests

| Contract | Named test |
|---|---|
| The taxonomy validates in registered order and normalises with its case map | `config/test_taxonomy.py::test_shipped_taxonomy_validates_in_registered_order` |
| Invalid taxonomies are refused | `::test_invalid_taxonomies_are_refused`, `::test_direct_construction_is_validated` |
| The single-label priority rule is deterministic | `nlp/test_topics.py::test_single_label_priority_rule_deterministic` |
| Case map and stem matching | `::test_case_map_and_prefix_matching` |
| Assignment uses the frozen taxonomy digest | `::test_uses_frozen_taxonomy_hash` |
| Assignment reads only as-of text | `::test_assignment_reads_only_as_of_text` |
| A video title is never assigned | `::test_video_title_not_used_for_assignment` |
| The audit sample is seeded and stratified | `eval/test_topic_audit.py::test_sample_is_seeded_and_stratified` |
| Audit items carry no timestamp or episode identifier | `::test_audit_items_carry_no_timestamp_or_episode_id` |
| A development audit samples the pre-origin span only | `::test_development_audit_samples_pre_origin_span_only` |
| Wilson intervals and Cohen's kappa match known values | `::test_wilson_interval_known_values`, `::test_cohen_kappa_known_values` |
| Precision, recall and complete annotation | `::test_audit_metrics_and_recall_floor` |

Open: whether the real keyword lists, which reveal the target language, are kept
in the repository or outside it with only their digest recorded; decided before
the pilot.
