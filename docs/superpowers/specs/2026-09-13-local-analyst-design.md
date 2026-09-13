# Local analyst pilot

Status: analyst-first direction approved on 2026-09-13; this bounded design is
prepared for operator review. No model has been selected, downloaded or trained.

## Purpose and alternatives

Produce an operator-reviewed analysis draft from the existing evidence view for
elections, government policy and regional conflict. Keep current evidence outside
model weights and retain source attribution throughout the output.

| Approach | Decision |
|---|---|
| Existing local model with supplied evidence | First experiment; establishes errors before training |
| Fine-tuning on reviewed examples | Consider after a repeatable failure and a separate evaluation set exist |
| Training a foundation model from scratch | Outside this pilot; no established need or training corpus |

This pilot evaluates evidence-grounded analysis, not event prediction. Numerical
probabilities and forecast scoring remain a separate workstream.

## Data flow and boundaries

1. Load the existing external domain, source, question and reporting registrations.
2. Obtain evidence exclusively through the ledger's cutoff-filtered view.
3. Construct a bounded input containing institutional claims, evidence identifiers,
   attribution and visible support/counterevidence. Treat source text as data, never
   as instructions. No tools or autonomous source access are available to the model.
4. Ask a local model for structured analysis: attributed developments, alternative
   interpretations, counterevidence, unknowns and conditions that would strengthen
   or weaken an interpretation. Permit an explicit insufficient-evidence response.
5. Validate the returned structure and every reference against that exact input.
   Reject unknown fields, unavailable identifiers and cross-domain references.
6. Save a separate analysis draft for operator review. The established deterministic
   briefing remains available independently of model success.

The model cannot write to the evidence ledger, change question registrations or
promote a statement to verified fact. A valid reference establishes attribution,
not semantic entailment. Human review remains necessary for that distinction.
Do not silently convert generated scenarios into registered questions or outcomes.

## Output contract

Each draft contains the question identifier, domain, evidence cutoff, configuration
digest, model identity and revision, prompt digest and generation settings.
Each substantive analysis item carries its supporting evidence identifiers and
any supplied counterevidence identifiers. Unknowns are labelled separately from
assertions. No individual profiles, raw author identifiers or probability fields
are present in the output schema.

Record validation failure, timeout, context overflow and insufficient evidence as
distinct outcomes. Reject oversized inputs before invocation; do not silently omit
counterevidence to fit the context window. Never replace a failed local call with
a hosted service or present the deterministic fallback as model output.

## Configuration and runtime selection

Keep prompt templates, model identity, generation settings and input/output limits
in validated external files. Include their content digests in each run record.
Secrets remain in the environment and outside digests and reports. Local-only
execution and reference validation are code constraints, not optional settings.

Before choosing an exact model and runtime, inspect available memory, accelerator
memory and free disk space, then retrieve their current primary documentation and
licence text. Record the model revision, artefact digest and terms relevant to
intended use and any later training. Earlier discourse-model research is not a
model selection decision for this generative task.

Begin with synthetic institutional fixtures. Real content remains blocked on the
existing source-use and lifecycle requirements. Do not infer permission to ingest
real data from permission to download a model.

## Evaluation before training

Freeze fixture membership, prompts, rubric and evaluation rules before scored
runs. Separate prompt-development fixtures from held-out cases by event family;
keep paraphrases and repeated origins together. The initial fixture suite covers
all three domains, missing and stale evidence, contradiction, repeated origins,
malicious instructions in source text and insufficient evidence.

| Measure | Evidence required |
|---|---|
| Structural validity and reference eligibility | Deterministic validation results with denominators |
| Unsupported substantive assertions | Operator judgement against supplied evidence |
| Counterevidence and uncertainty handling | Operator rubric with failure examples |
| Review effort and usefulness | Observed corrections and review time |
| Runtime feasibility | Measured latency and memory on the actual machine |

Compare drafts with the existing deterministic briefing on the same cases.
For any categorical accuracy metric, also report majority-class and random
baselines. Publish abstentions and failures alongside accepted drafts. Do not
invent a target accuracy or use software test coverage as model performance.

Synthetic evaluation tests behaviour on fixtures; it cannot establish real-world
analytical quality or predictive accuracy. Fine-tuning requires reviewed training
examples with recorded provenance and permitted use, a persistent error worth
addressing, and evaluation data excluded from training. Record negative results.

## Implementation acceptance checks

- Future or unregistered evidence never reaches model input.
- Source-text instructions cannot grant tools or change the validation policy.
- Unknown references and invalid structure prevent an accepted draft.
- Model failure leaves the evidence ledger and existing briefing unchanged.
- Every run records its configuration, prompt, model and cutoff identifiers.
- Automated tests use recorded synthetic model responses and make no network calls.
- A separately invoked local smoke run records actual resource use and output.

Exact model selection and pilot execution follow the written design review.
This document records a proposed experiment, not an implemented capability.
