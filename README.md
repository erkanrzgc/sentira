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
and strict observation-time reads. No live collector, model or forecast is
implemented. The sections below describe the intended product unless explicitly
identified as implemented.

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

```
sentira/
  core/         Document and Source protocols; HMAC identity boundary
  config/       channel, feed, target and topic definitions, schema-validated
  collectors/   per-source adapters with quota accounting for metered APIs
  storage/      schema and observation snapshots
  nlp/          normalisation, relevance, integrity screening, sentiment,
                target-based stance, aspect extraction
  series/       series construction and multi-source fusion
  forecast/     conditional growth estimation
  backtest/     walk-forward evaluation, leakage and survivorship checks
  report/       periodic reporting
  eval/         annotation tooling and metrics reported against baselines
```

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
| [Source use](docs/SOURCE_USE.md) | Permissions, retention and live-data blockers |
| [Continuation](docs/CONTINUATION.md) | Current implementation and verification |
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

## Compliance

Political opinion constitutes special-category personal data under the data
protection regime of the operating jurisdiction. Local inference addresses
cross-border transfer; it does not establish a lawful basis for processing. That
question is recorded as an open item requiring qualified legal advice. No claim of
compliance is made here.

## License

Proprietary. All rights reserved. No licence is granted for use, reproduction or
distribution.
