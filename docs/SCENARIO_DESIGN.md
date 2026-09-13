# Three-domain scenario analysis

Status: product direction approved on 2026-09-13; detailed design prepared for
review. This is a design increment, not an implemented forecasting capability.

## Purpose and first user

The first user is the operator, reviewing public developments and producing a
personal briefing. Commercial institutional reporting is a later stage, dependent
on demonstrated utility and source-use conditions. The first three domains are
elections, government policy and regional conflict.

The output answers: what changed, which scenarios are consistent with the available
evidence, what argues against them, and what observation would change the analysis?
It does not claim knowledge of undisclosed decisions.

## Relationship to the existing system

The aggregate discourse series and its conditional-growth evaluation remain intact.
They measure expressed attention and tone. Neither comment volume nor a stance
distribution is a representative estimate of voting intention or conflict risk.

Scenario analysis is a separate, experimental product track. Its inputs are public
institutional evidence and permitted aggregate data; its outcomes require their
own definitions and evaluation. The existing BACKTEST T1 endpoint does not validate
election, policy or conflict predictions. An explanatory scenario is not a scored
forecast, and a future forecast is not a statement of fact.

All existing privacy constraints remain binding. There is no account dossier,
individual political-affiliation inference or targeted persuasion output. Named
personnel-change forecasting is outside this increment. Stance target types are
not expanded to accommodate it. Regional conflict analysis concerns public
institutional developments, not tactical locations, targeting or operational
military advice.

## Approaches considered

| Approach | Benefit | Limitation |
|---|---|---|
| **One evidence system, three domain briefings** | Shared provenance and reporting rules; domain-specific questions remain explicit | Initial output is qualitative and operator-reviewed |
| Three separate forecasting models | Independent specialisation | Requires three suitable datasets and outcome protocols before useful claims |
| Free-form local model responses | Quick demonstration | Sources, reproducibility and uncertainty are difficult to audit |

Use the shared evidence approach. A local model may later assist extraction and
drafting, but it cannot create evidence, confirm an event or invent probabilities.
The first offline report workflow requires no model download.

## Initial domain contracts

The horizons below are proposed engineering defaults, not measured attention
lifetimes. They are frozen per question before evidence-based evaluation starts.

| Domain | Initial question family | Horizon | Admissible inputs | First output |
|---|---|---|---|---|
| Elections | What changed in the official timetable, rules or aggregate published evidence relevant to the next registered milestone? | Explicit milestone date configured by the operator | Official electoral publications; permitted aggregate surveys with disclosed methodology; public institutional statements | Evidence-supported scenarios, methodological limitations and next milestones; no vote-share projection |
| Government policy | Will a specifically named institutional proposal reach a defined formal stage? | 7 or 30 days from issue time | Official notices, legislative records, institutional statements and permitted reporting | Scenarios distinguishing announcement, proposal, adoption and implementation |
| Regional conflict | Will a defined public diplomatic or institutional escalation/de-escalation event occur? | 7 or 30 days from issue time | Public institutional statements, published agreements and permitted corroborating reports | Escalation/de-escalation scenarios with competing explanations; no incident targeting |

Broad questions such as whether an election will go well or whether war will
happen must be narrowed before entering the forecast ledger. A conflict question
must specify parties at the institutional level, event definition and geography
in the private operating profile. The published examples remain generic.

## Evidence contract

One evidence record concerns one attributed claim. A source making a statement is
evidence that the statement was made, not automatic proof of its substance.

| Field | Contract |
|---|---|
| `evidence_id`, `source_id` | Stable internal references; source must be registered |
| `domain_ids` | One or more of the three fixed domains |
| `source_url` | Original public source locator; no credential-bearing URLs |
| `published_at`, `observed_at` | Distinct aware UTC timestamps; storage supplies observation time |
| `claim`, `attribution` | Minimal permitted paraphrase and institutional attribution; no account identifier |
| `original_source_group` | Links syndicated/repeated reports to the same origin; repetition is not independence |
| `evidence_status` | `attributed`, `corroborated`, `contested` or `insufficient`; not a probability scale |
| `support_ids`, `contradiction_ids` | Existing evidence references only; absence of contradiction is not confirmation |
| `rights_record_id`, `expires_at` | Source-use and retention requirements; missing permission prevents real ingestion |
| `content_digest`, `revision_of` | Integrity and revision provenance; a digest is not a substitute for unavailable source text |

Do not retrofit these records into `Document` by accepting new live provenance or
loosening its fields. Implement a dedicated evidence contract and storage adapter
after review. Reuse HMAC, timestamp validation and the single storage read boundary.
The existing foundation stays synthetic-only until real-data controls are ready.

Evidence revisions are new observations while retention permits them. Prior
briefings keep references to the version they used. Required deletion can make an
old briefing unreproducible; the system must state that rather than silently using
the replacement. No indefinite archive is assumed.

## Briefing contract

Generate an on-demand Markdown briefing first. The proposed default is a 24-hour
change window, configured separately from each scenario's horizon. Each briefing
has an issue timestamp, an evidence cutoff and the configuration digest.

For each domain, show:

1. Changes since the previous briefing and coverage gaps.
2. Attributed developments with evidence references.
3. One to three plausible scenarios, including a continuation scenario when
   supported. Do not manufacture scenarios merely to fill a template.
4. Supporting evidence, counter-evidence and material unknowns for each scenario.
5. Observable triggers that would strengthen or weaken the scenario.
6. The next review date or registered public milestone.

When evidence is insufficient, print that finding in place of a scenario. A
fetch failure is a coverage gap, not evidence that nothing happened. Do not turn
these labels into an implied low/medium/high probability ranking.

No automatic distribution, scheduling, client dashboard, numerical probability or
model-generated factual assertion is part of the first slice. The operator reviews
the draft before treating it as an analytical briefing.

## Configuration and clean-code boundaries

Use UTF-8 TOML for the first file-backed configuration, parsed with Python 3.12
`tomllib`. These are planned files; no loader or files ship in this design change.

| Planned file | Contents |
|---|---|
| `config/domains.toml` | Domain identifiers and display labels |
| `config/sources.toml` | Registered endpoints, provenance groups and rights-record references |
| `config/questions.toml` | Questions, horizons, event definitions, resolution sources and invalidation rules |
| `config/reporting.toml` | Change window, output format and evidence freshness rules |
| Environment / untracked `.env` | API credentials and HMAC keys |

Published examples contain synthetic institutions, generic roles and no operating
jurisdiction, target language or client. Real operating profiles are kept outside
version control and selected by an explicit path. Validate unknown fields,
duplicates, cross-references, timezone awareness and horizon ordering at load.
No executable expressions or dynamic imports are accepted in configuration.

Configuration changes receive a new digest; reports retain the digest they used.
Question definitions cannot be overwritten after issuance. Secrets are excluded
from digests and reports. Configuration cannot disable privacy, evidence-cutoff or
endpoint restrictions. Source text is untrusted data and cannot change instructions,
tools, configuration or permissions.

## Forecast ledger: later, separately evaluated

A forecast record requires a precise question, issue time, cutoff, resolution
deadline, permitted resolution source, outcome rule and immutable version.
Resolution states are `pending`, `yes`, `no`, `unresolved` and `invalidated`.
Missing evidence or cancelled events must follow the registered rule, not silently
count as incorrect or disappear from the report.

The first briefing does not emit probabilities. Before enabling them, register
baserate comparisons, a prospective evaluation protocol, scoring rules and a
minimum evidence requirement appropriate to each question family. Report all
issued forecasts, coverage and unresolved outcomes; do not select only successful
examples. The existing surge-count threshold is not transferred to these domains.

## First implementation slice and acceptance criteria

Implement a synthetic evidence ledger, validated file configuration and a
deterministic Markdown renderer before a source collector or local model.

| Acceptance criterion | Planned test |
|---|---|
| All three domains render through the same pipeline | `test_three_domains_share_briefing_pipeline` |
| Configuration is loaded from files; unknown fields/references fail | `test_invalid_briefing_config_rejected` |
| Same inputs, cutoff and config digest produce identical output | `test_briefing_is_deterministic` |
| Future observations cannot alter an earlier briefing | `test_briefing_ignores_future_evidence` |
| Missing evidence IDs cannot produce a supported claim | `test_unknown_evidence_reference_rejected` |
| Repeated origin groups do not count as independent corroboration | `test_syndicated_claims_share_one_origin` |
| Missing source coverage and contradictory evidence remain visible | `test_gaps_and_counterevidence_are_reported` |
| Synthetic output is unmistakably labelled and contains no probabilities | `test_synthetic_briefing_has_no_forecast_probability` |
| No network or hosted inference is invoked | `test_briefing_runs_offline` |

These are future software checks, not measured results. Qualitative utility is
then assessed by the operator: can each conclusion be traced, can changes be
identified, and does the briefing reduce review effort? Record shortcomings as
well as useful observations. Do not assign an invented success percentage.

## Delivery order

1. Review this detailed design and the synthetic sample briefing.
2. Write and execute the bounded offline briefing implementation plan.
3. Resolve rights, retention and deletion for a small registered source set.
4. Add source adapters through official APIs or registered publisher feeds where
   the repository agreement permits them. No scraping or arbitrary webpage fetcher.
5. Evaluate local-model assistance against operator-reviewed extraction examples.
6. Introduce the separately registered prospective forecast ledger if the evidence
   supports it; expand domains only after the first three demonstrate utility.
