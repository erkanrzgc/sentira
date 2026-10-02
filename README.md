# Sentira

**Foresight for public discourse — aggregate agenda, tone and early signal.**

[![Status](https://img.shields.io/badge/status-research%20preview-orange)](#status)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Models](https://img.shields.io/badge/inference-local--only-success)](#design-principles)
[![Privacy](https://img.shields.io/badge/design-aggregate--only-informational)](#design-principles)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)](#license)

Sentira is designed to observe public commentary and news metadata and convert them into time
series: which subjects gain attention, when they gain it, and in what tone
institutions are discussed. The product is designed to exclude person-level reporting. The offline
foundation is not a complete production privacy boundary.

**Implemented now:** a Python 3.12 foundation for synthetic data, with validated
documents, HMAC identity separation, restricted target types, atomic SQLite writes
and strict observation-time reads. A separate synthetic evidence ledger renders
three-domain Markdown briefings from external TOML files. No live collector, analyst model
or numerical forecast is implemented. The sections below describe the intended product unless explicitly
identified as implemented.

**New product direction:** operator-reviewed scenario briefings for elections,
government policy and regional conflict. The [detailed design](docs/SCENARIO_DESIGN.md)
and [fictional sample](docs/SCENARIO_SAMPLE.md) define the approved direction.
The offline briefing is implemented; its qualitative usefulness and forecasting
value have not been validated by the discourse-growth protocol.

**Offline procedural case pilot:** a separate `case-report` command lists
synthetic case evidence by observation cutoff, with source/page references,
explicit gaps and supersession review flags. It infers no legal finality.
See the [case register design](docs/superpowers/specs/2026-09-25-case-register-design.md).

```powershell
python -m sentira.cli case-report --input examples/synthetic-cases.toml --cutoff 2030-02-03T00:00:00Z --issued-at 2030-02-03T00:00:00Z --output out/cases.md
```

Existing output requires `--overwrite`. Cases, institutions, source references,
events and reporting labels live in TOML. Only explicitly synthetic input and
reserved source URLs are accepted, and each event link must share the host of
its registered source; this is not a semantic personal-data filter.
Observation timestamps are supplied per snapshot, not durably captured by a
collector. There is no automated document reading, network access or model call.

A separate [synthetic OCR experiment](experiments/ocr/README.md) now measures
local field recovery on fictional PDF pairs. It is not connected to case reports
or real-source ingestion. [Development findings](experiments/ocr/RESULTS.md)
include failures on smaller, lower-resolution text; they establish no production
document-reading accuracy.

The [synthetic field-review workflow](experiments/field_review/README.md) keeps
OCR candidates pending until an explicit field decision is supplied. Decisions
are bound to source-page and result digests. This is a separate development
workflow, not independent human validation or case-ledger integration.

---

## What the system produces

The unit of output is an interval-indexed series:

```
topic × target × interval  →  { volume, tone distribution, integrity flags }
```

From this, three artefacts follow: a periodic report describing how attention and
tone moved; alerts when a subject already in motion is likely to grow further; and
retrospective measurement of how far a known event displaced attention and for how
long.

Targets are institutional. Topics are drawn from a declared taxonomy. Neither is
free-form, and the offline configuration loader rejects unsupported target types. Full
collection and topic configuration remain planned.

## Method

```
collect → normalise → filter relevance → screen integrity
        → score sentiment and stance → aggregate → report
```

Each stage is a module with a single responsibility, communicating through one
`Document` interface. Sources are pluggable, and the fusion boundary is
multi-source from the outset even where a single collector is implemented.

Language handling is a configured concern rather than a general one. The
normalisation, relevance and stance layers are built for one language at a time and
tuned to its morphology and its informal register; portability across languages is
not claimed.

Two properties receive particular attention because they are ordinarily got wrong:

**Point-in-time correctness.** Documents carry both a publication time and an
observation time. Cumulative counters are never stored on the document; they are
recorded in a snapshot table keyed by observation and read only from observations
made at or before *T*. Material retrieved after *T* contributes only its immutable
fields, and only where the registered collection policy would have retrieved it by
*T*; every value so derived is flagged as reconstructed. The offline implementation provides strict observation-time reads only.
Historical replay is conditional on visibility evidence; survivor-only
reconstruction cannot establish exact past visibility.

**Survivorship measurement.** Historical retrieval returns only material that still
exists; moderation and deletion are not independent of political content. The bias
cannot be removed, but it can be quantified — continuous collection running
alongside historical retrieval serves as a control, and every retrospective result
is reported together with its uncorrected survival rate.

## Scope and limitations

Stated as prominently as the capabilities, because the boundary is the argument.

**Not a substitute for survey research.** Social platforms do not yield
representative samples: platform demographics are skewed, coordinated activity
occurs, and non-participants are unobserved. Sentira reports what was expressed and
when, not what a population holds.

**Not an instrument for tracking individuals.** Author identifiers are hashed at the
collector boundary using HMAC-SHA256 with the platform name included in the input,
so identical identifiers receive different hashes across platforms. This
does not prevent linkage through content or other information. The schema carries no raw-identifier
column, and tests assert this against the schema itself.

**Not an open target list.** Stance targets are restricted by schema to political
parties, state institutions and formally declared candidates; journalists,
academics and private individuals are rejected at load. Hashing authors alone would
be insufficient — leaving the target side unrestricted would permit tone toward a
named individual to be reconstructed from a hashed corpus. The two constraints
operate together.

**Foresight is bounded by the evidence.** The literature reviewed here supports investigation of
conditional growth estimation — whether a subject already in motion will grow
further — but provides no validated result here for subjects not yet visible. The system
claims the former only.

The separate scenario track explores broader institutional questions through
attributed evidence and explicit uncertainty. It introduces no validated prediction
claim or numerical probability; prospective forecasts require a separate protocol.

## Design principles

**Constraint by construction.** The offline schema and tests enforce a limited set of identity and temporal
contracts. Production privacy additionally requires lifecycle controls, access
restrictions, text handling and output suppression.

**Local inference.** All models run on local hardware; no content is sent to a
hosted inference service. This avoids hosted inference transfers; it is not a claim about every data flow. It
does not by itself establish a lawful basis for processing, and no such claim is
made.

**Provenance on every figure.** Each quantity records how it was obtained —
*calculated* (arithmetic), *measured* (observed directly), or *verified* (confirmed
against a primary source). Estimates are not presented as measurements.

## Architecture

Implemented in the offline foundation:

```
sentira/
  core/         Document envelope, HMAC identity boundary, synthetic evidence,
                procedural case records and registration helpers
  config/       target, briefing, case, quota, collection-policy and volume
                configuration, schema-validated
  storage/      document schema, observation snapshots, strict as-of reads,
                the synthetic evidence ledger and the quota ledger
  collectors/   metered client (every call debited before it is made), the
                polling schedule and replay visibility under policy P, and
                the calculated quota cost of P (synthetic only; no source
                adapter)
  report/       scenario briefing and case report rendering
  series/       surge episodes on strict as-of synthetic series
  backtest/     locked surge registration and per-cell positive counts
  cli.py        briefing, case-report, measure, lock, count and cost commands
```

Planned, not yet implemented:

```
sentira/
  collectors/   per-source adapters behind the metered client
  nlp/          normalisation, relevance, integrity screening, sentiment,
                target-based stance, aspect extraction
  series/       series construction from collected rows and multi-source fusion
  forecast/     conditional growth estimation
  backtest/     walk-forward evaluation, leakage and survivorship checks
  eval/         annotation tooling and metrics reported against baselines
```

The local experiments under `experiments/` sit outside the package and are not
connected to it.

Accuracy figures are reported alongside a majority-class and a random baseline. A
figure without its baseline is not reported, on the grounds that a three-class
problem with skewed priors admits high nominal accuracy from a trivial classifier.

## Applicability

The pipeline is not specific to one client or one election. Differences between
applications reduce to configuration — target and topic definitions — while
collection, language processing and scoring remain unchanged.

| Application | Use |
|---|---|
| Public institutions | Service satisfaction; early identification of complaint clusters |
| Organisations | Reputation measurement; crisis signal; campaign response |
| Media | Agenda analysis; data journalism |
| Research | Evolution of public attention over time |

## Status

**Research preview. Offline foundation for synthetic data only.**

The repository holds design documentation, an offline foundation and its tests. Implementation
proceeds in an evidence-first order: feasibility and accuracy are established before
feature work, on the principle that a capability which cannot be measured cannot be
represented to a client.

Claims in `docs/` are labelled by how they were established. Underlying research
material is held separately.

| Document | Contents |
|---|---|
| [Offline scope](docs/IMPLEMENTATION_START.md) | Approved first implementation and limits |
| [Data pilot](docs/DATA_PILOT.md) | Source qualification and manual evaluation before models |
| [Source use](docs/SOURCE_USE.md) | Permissions, retention and live-data blockers |
| [Continuation](docs/CONTINUATION.md) | Current implementation and verification |
| [Scenario design](docs/SCENARIO_DESIGN.md) | Three-domain briefing contracts and implementation boundaries |
| [Scenario sample](docs/SCENARIO_SAMPLE.md) | Entirely fictional example of the proposed briefing |
| [Concept](docs/CONCEPT.md) | Definition, boundaries, commitments, open items |
| [Roadmap](docs/ROADMAP.md) | Design status, decisions carried forward, validation criteria |
| [Backtest](docs/BACKTEST.md) | Evaluation protocol, phase order, first implementation files |
| [Feasibility](docs/FEASIBILITY.md) | Collection volume and cost, platform access, local throughput |
| [Forecasting](docs/FORECASTING.md) | Evidence bounding the foresight claims; leakage controls |
| [Models](docs/MODELS.md) | Licence inheritance through distillation; model selection |
| [Components](docs/COMPONENTS.md) | Survey of reusable open-source components (unverified) |

## Requirements

The offline foundation uses only the Python standard library and needs no GPU or
API credentials. The model-related requirements below concern later phases.

- Python 3.12; later versions are ahead of the machine-learning stack used here
- A CUDA-capable GPU is recommended for local inference. The pipeline is designed
  to operate within 8 GB of video memory
- Credentials for metered sources are supplied through environment variables; see
  `.env.example`

## Run the offline checks

From a local checkout in PowerShell:

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m pytest --cov=sentira --cov-branch --cov-fail-under=80
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m ruff format --check .
```

On Linux or macOS, where `python3` may not be 3.12, name the interpreter explicitly:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m pytest --cov=sentira --cov-branch --cov-fail-under=80
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
node --test tests/experiments/review_screen.test.cjs tests/experiments/review_screen_app.test.cjs
```

The same checks run in continuous integration on every push and pull request
(`.github/workflows/ci.yml`). The Node.js step covers the review-screen scripts;
without Node.js the cross-language Python check is skipped.

Dependency installation may access the package index; the tests block network
connections and use original synthetic fixtures. The end-to-end example is
`tests/test_offline_e2e.py`: it hashes synthetic identifiers, writes a document and
counter snapshot, adds a later snapshot, then verifies the earlier view after
reopening storage. It produces no model accuracy or forecasting claim.

The database is disposable synthetic storage. A `synthetic` provenance declaration
cannot prove that arbitrary supplied text is synthetic. Do not ingest real content:
retention, refresh/deletion, access controls and output suppression are not yet
implemented. Target validation checks the declared type, not documentary evidence
that a real entity qualifies. See [current limits](docs/CONTINUATION.md).

## Count surges in a synthetic series

The measured addendum is computed once from the pre-origin span and locked with the
registration before counting. The example files are already measured and locked;
to repeat the first two steps, write to new paths:

```powershell
./.venv/Scripts/python.exe -m sentira.cli measure `
  --registration examples/synthetic-registration.toml `
  --series examples/synthetic-series.toml --output out/measured.toml
./.venv/Scripts/python.exe -m sentira.cli lock `
  --registration examples/synthetic-registration.toml `
  --measured out/measured.toml --series examples/synthetic-series.toml `
  --output out/registration.lock
./.venv/Scripts/python.exe -m sentira.cli count `
  --registration examples/synthetic-registration.toml `
  --measured examples/synthetic-measured.toml `
  --lock examples/synthetic-registration.lock `
  --series examples/synthetic-series.toml --output out/synthetic-count.md
```

The command verifies the registration lock before reading the series and refuses
any changed definition. It counts episodes, eligible, positive, negative, censored
and detected-at-crossing episodes for every registered grid cell, separately for
the test span from the first origin and for the pre-origin span, which is never a
test fold. It applies the registered primary-and-fallback rule to the test span
only and stamps both registration digests into the report. The fictional example is far below *K*min and is reported as not
backtestable. Counting recomputes the measured addendum from the series and
refuses any difference. The measurement rules are a proposal for synthetic
development; topic assignment and integrity screens are not implemented, and
visibility is strict observation time only. See the [surge-counting design](docs/superpowers/specs/2026-10-02-surge-counting.md).

## Quota ledger

The metered client in `collectors/quota.py` debits the persistent ledger before
every call and settles the outcome afterwards; a failed call stays spent. The
policy (`examples/synthetic-quota.toml`) fixes the daily units, the live,
retrieval, survival and buffer reservations, the quota-day offset and the
registered read-only endpoints; search is always refused. Retrieval cannot spend
the live reservation. `drain` serves one purpose per run, so on exhaustion it
stops that queue cleanly and hands back what it collected. Only synthetic
transports exist; no API client or credential is implemented. See the [quota-ledger design](docs/superpowers/specs/2026-10-02-quota-ledger.md).

## Polling schedule and replay

`collectors/policy.py` applies the registered collection policy P
(`examples/synthetic-policy.toml`): no poll before discovery, missed ages
coalesced into one immediate poll, later ages anchored to publication, and
completed ages kept across a restart. The same schedule gives the replay time of
a retrieved thread, or none where the page cap or the last poll age would have
hidden it. Replay is checked against an independent synthetic provider, not
recorded responses, and is not yet wired into the as-of reader. See the
[collection-policy design](docs/superpowers/specs/2026-10-02-collection-policy.md).

## Project the quota cost

```bash
.venv/bin/python -m sentira.cli cost \
  --policy examples/synthetic-policy.toml --quota examples/synthetic-quota.toml \
  --volume examples/synthetic-volume.toml --output out/synthetic-cost.md
```

The command costs policy P on its own schedule against assumed volumes and the
quota reservations: discovery and polls against the live reservation, and the
days of retrieval one history-year needs, with threads lost to the page cap or
posted after the last poll age. Every figure is calculated; channels, videos per
day and thread strata are fictional assumptions until a live run measures them. An overrun of the live reservation is stated, never absorbed by
the buffer. See the [cost-projection design](docs/superpowers/specs/2026-10-02-cost-projection.md).

## Generate a synthetic briefing

After installing the development environment above:

```powershell
./.venv/Scripts/python.exe -m sentira.cli briefing `
  --config config --evidence examples/synthetic-evidence.toml `
  --observed-at 2030-01-01T12:00:00Z --cutoff 2030-01-01T12:00:00Z `
  --issued-at 2030-01-01T12:00:00Z --output out/synthetic-briefing.md
```

The command creates a disposable in-memory ledger and a Markdown file. Explicit
observation and issue times belong to a fictional simulation, not a live replay.
Use `--overwrite` only to replace an existing output. No model, credentials or
network connection is needed. All sources use reserved, non-resolving URLs.

| File | Operator-controlled content |
|---|---|
| `config/domains.toml` | Labels for the three supported domains |
| `config/sources.toml` | Fictional sources, origins and rights references |
| `config/questions.toml` | Versioned questions, scenarios and evidence references |
| `config/reporting.toml` | Registration time, freshness and change windows |
| `examples/synthetic-evidence.toml` | Attributed fictional evidence |

Unknown fields and references fail validation. A persistent `EvidenceLedger`
locks question definitions by identifier and records first observation; the CLI
creates a new simulation each run and does not preserve an issuance history.
Scenario text is authored in configuration, not generated by artificial
intelligence. Source-group counts measure registered origins, not independence
established through external investigation. Missing or stale support withholds
substantive scenario text; counterevidence and coverage gaps remain visible.

## Compliance

Political opinion constitutes special-category personal data under the data
protection regime of the operating jurisdiction. Local inference addresses
cross-border transfer; it does not establish a lawful basis for processing. That
question is recorded as an open item requiring qualified legal advice. No claim of
compliance is made here.

## License

Proprietary. All rights reserved. No licence is granted for use, reproduction or
distribution.
