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
| Ownership | A keyword belongs to one topic only, and a stem may not cover another keyword in any topic, so one word matches at most one keyword |
| Normalisation | A registered case map folds characters before lower-casing, so language-specific case folding is data, not code |
| Freezing | `frozen_at` and the content digest; assignment and the audit refuse a taxonomy whose digest differs from the registered one; the pilot lock records the digest and is refused before `frozen_at`, and a pilot takes the registered digest from its lock, so a taxonomy edited after the lock is refused |
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

BACKTEST §0.4 asks for the share of retrieved comments withheld because they were
edited after *T*. Under the strict rule implemented now that share does not arise:
storage refuses a row updated after it was observed, so a comment edited after *T*
was also observed after *T* and is not yet known at *T*. The share belongs to the
replay carve-out for retrieved rows and is reported when that is built.

## Audit and agreement set

| Element | Design |
|---|---|
| Sample | Seeded, per stratum: positive-episode, negative-episode and non-episode intervals, crossed with assigned and unassigned comments as the strata the caller supplies. A document enters once; a stratum smaller than the registered size is taken whole and its shortfall reported |
| Provenance | Candidates are built from an as-of comment and its assignment and keep its taxonomy digest; the draw refuses another digest or an unregistered topic, and holds the taxonomy and each stratum's population. The draw checks itself on construction, so a hand-built or edited draw meets the same rules, and an empty draw has no report |
| Span | A development audit draws only from before the first origin; a confirmatory audit only from after it |
| Blinding | Items carry an opaque identifier and the text; they are shuffled across strata; the key to documents, strata and assignments is kept apart |
| Size | About 100 items per stratum give a Wilson interval of roughly ±0.1 at a proportion of one half (*calculated*) |
| Metrics | Precision and recall per topic, each item weighted by its stratum's population over its sample, so the rates estimate the population rather than the sample; Wilson score intervals at the Kish effective sample size, an approximation that equals the plain Wilson interval when every weight is equal |
| Baselines | Accuracy beside the majority-class accuracy and the expected accuracy of a random assigner with the same assigned shares; per topic, the weighted prevalence and assigned share |
| Labels | An annotation is a registered topic or none; anything else is refused |
| Floor | Recall is compared with a registered floor through the lower interval bound; the floor is registered with the pilot |
| Agreement | Cohen's kappa between the first labelling and the blind re-labelling of 100 items after at least a week, paired by item identifier |

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
| Rates are weighted by stratum population | `::test_recall_is_weighted_by_stratum_population` |
| Accuracy is reported beside its baselines | `::test_accuracy_is_reported_beside_its_baselines` |
| Annotations name registered topics only | `::test_annotation_labels_must_be_registered_topics` |
| A short stratum is reported | `::test_short_stratum_is_reported_not_hidden` |
| Duplicates, other digests and unregistered topics are refused | `::test_draw_refuses_duplicates_foreign_digests_and_unknown_topics` |
| Candidates keep the assignment digest | `::test_candidate_carries_the_assignment_digest` |
| A draw checks itself | `::test_draw_validates_itself` |
| An empty audit has no report | `::test_empty_audit_is_refused` |
| A taxonomy edited after the lock is refused | `backtest/test_pilot.py::test_locked_taxonomy_digest_refuses_a_later_edit` |
| The pilot lock binds the taxonomy | `backtest/test_pilot.py::test_pilot_lock_binds_a_taxonomy_frozen_before_it` |

Open: whether the real keyword lists, which reveal the target language, are kept
in the repository or outside it with only their digest recorded; decided before
the pilot.
