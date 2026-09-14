# Source qualification and manual evaluation pilot

Status: data-first direction approved on 2026-09-13. Source qualification and the
evaluation protocol are prepared; no live collector or model is enabled.

## Scope and source roles

Maintain a small source register outside the published repository. Concrete
institutions, operating geography and source-specific research remain private.
The register records retrieved documentation and failed retrievals separately.
Searching documentation is not an operational collection or a measured API test.

| Role | Intended evidence | Current project disposition |
|---|---|---|
| Electoral authority | Timetables and aggregate certified outcomes | Qualify official access and reuse before ingestion |
| Legislature | Proposal, committee, adoption and publication stages | Qualify a documented access route; do not infer one from an old feed reference |
| Official gazette | Formal publication and effective-date evidence | Resolve documentation retrieval and permitted access |
| Diplomatic institution | Attributed institutional positions | Publisher feed is a candidate, not automatically an authorised API |
| Humanitarian document index | Context and separately attributable reports | Qualify API registration and original-publisher rights |
| Media-event index | Discovery and media coverage metadata | Never use machine-coded events as ground truth or article rights |

These roles are candidates, not an enabled production source list. The first
selection excludes social comments, individual records, model-generated labels
and unspecified survey aggregators. Add an aggregate survey only with methodology,
field dates, population, sample design and applicable reuse evidence.

## Qualification record

For each candidate, record the official documentation URL, actual review date,
retrieval outcome, verified capability, unresolved capability and next action.
Separate these permissions: access, local storage, derived analysis, redistribution
and training. Unknown permission stays unknown; access does not imply the others.

Record exact endpoint and method, authentication, documented quota, permitted
fields, update/deletion behaviour and historical coverage before enabling access.
Do not assign a historical start date from a provider's general archive description
to a different endpoint. A published quota is verified documentation, not measured
project allocation. Record redirects and unavailable pages without bypassing them.

The repository agreement currently requires official APIs. A publisher RSS page
can establish feed availability but does not by itself satisfy that requirement.
Resolve this explicit policy boundary before a feed collector is implemented;
do not silently interpret it as an exception. Manual documentation review remains
separate from production ingestion.

## Retention decisions before real evidence storage

| Data class | Required recorded decision |
|---|---|
| Raw response or document text | Permission, maximum duration, refresh interval and deletion trigger |
| Extracted claim and source link | Whether derived retention is permitted; correction propagation |
| Human annotation | Source dependency and rights; independent reviewer-authored text distinction |
| Exported report | Suppression/correction procedure and expiry obligations |
| Backups and logs | Expiry, content minimisation and deletion propagation |

There is no universal retention duration in this pilot. Set source-specific values
only after the supporting terms or permission have been reviewed. The synthetic
ledger's expiry filter does not implement these controls. Hashes alone neither
establish reuse rights nor preserve reproducibility after required deletion.

## Manual evaluation protocol

Start with a proposed 18-case worksheet: six cases in each of three domains
(calculated: 3 x 6). This is a workload choice, not a statistical power estimate
or a completed dataset. No model is required to author or review it.

| Case family in each domain | Expected distinction |
|---|---|
| One attributed institutional statement | Statement versus independently established event |
| Formal stage change | Proposal versus adoption; announcement versus implementation |
| Counterevidence | Competing evidence remains visible |
| Repeated origin | Multiple URLs do not imply independent confirmation |
| Missing coverage | Missing evidence does not establish absence of an event |
| Temporal trap | Later observation or correction cannot enter an earlier evidence packet |

Allocate four event families per domain to development and two to held-out review
(calculated: 12 and 6). This split is provisional until actual cases are selected.
Keep every revision, paraphrase and syndicated copy of an event in the same split.
Assign the split before drafting reference answers. Do not claim independence if
the same author has already used the held-out answers to improve the workflow.

Every case records: case and event-family identifiers, domain, question, publication
and observation timestamps, cutoff, rights record, source and origin identifiers,
available evidence, unavailable evidence with reason, proposed reference answer,
prohibited inference, reviewer decision and review date. Keep later outcomes in a
separate answer-only field. Source eligibility must pass before storing real text.

For historical material observed today, the default is a current retrospective
reading. Do not backdate observation to publication or call it a historical replay.
Freeze case membership, evidence packet digests, splits and rubric before scoring.
Changes create a new registration; do not overwrite a scored version.

## Review rubric

| Check | Record |
|---|---|
| Attribution | Every substantive assertion maps to eligible evidence |
| Entailment | Evidence supports the asserted meaning, not just a related topic |
| Stage | Formal status and dates are accurately distinguished |
| Counterevidence | Relevant disagreement is preserved |
| Independence | Origins, not URLs, support corroboration claims |
| Time | No evidence unavailable at cutoff is used |
| Uncertainty | Gaps and alternative explanations are explicit |
| Usefulness | Operator corrections and observed review time |

Use pass, fail or not-assessable with a short reason and source reference for each
check. Preserve the original answer and corrections. One operator's review is not
independent validation. Machine-drafted reference answers remain unreviewed until
a human confirms them; never label them as human ground truth automatically.

Begin by reviewing the existing deterministic briefing. Report counts and
denominators, missing cases and unresolved disagreements. If categorical accuracy
is later reported, include majority-class and random baselines. Do not combine
these dimensions into a single invented quality score.

## Model decision

The local analyst design is deferred. First identify a recurring, measured manual
bottleneck in the reviewed cases. Only then propose a bounded local-model comparison
on the same task. Fine-tuning requires a further decision after evidence of a
persistent failure and an uncontaminated evaluation set exist.

## Completion ledger

- Source roles and qualification questions: prepared.
- Source-specific documentation review: recorded privately, including access gaps.
- Evaluation worksheet and rubric: prepared, not populated with 18 real cases.
- Three private source-grounded development reading drafts: prepared on 2026-09-14,
  with short original summaries and links; no human review completed.
- Qualified retained evidence packets, human reference answers and scored results:
  not produced. Date-only observation notes are not eligible for scored replay.
- Live collection, model download and training: not started.

The next deliverable is a qualified source record and one eligible evidence packet
per domain. Where a source cannot qualify, record the gap and seek a permitted
alternative; never fill a case with invented real-world evidence.
