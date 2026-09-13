# Concept

This document defines what Sentira is and, with equal weight, what it is not.
Feasibility figures are recorded in [FEASIBILITY.md](FEASIBILITY.md); design status
and validation criteria in [ROADMAP.md](ROADMAP.md).

The name derives from Latin *sentire*, to perceive or to feel, the root of
*sentiment*. It has a single spelling in code and in prose: `sentira`.

---

## 1. Definition

**Sentira measures public digital discourse at the aggregate level.**

It records which subjects rise and when, in what tone institutions are discussed,
and how that tone moves over time.

## 2. What it is not

The approved product direction now also includes an experimental institutional
scenario track for elections, government policy and regional conflict. See
[SCENARIO_DESIGN](SCENARIO_DESIGN.md) for the approved design and implemented synthetic slice. It complements
aggregate discourse measurement rather than treating it as a proxy for election
outcomes or conflict risk. No new forecasting capability is claimed, and all
person-level and source-use exclusions below continue to apply.

The boundary is stated before the capability. A product whose limits are not
written down in advance will be asked, later, for something it does not do.

### Not a survey

Social platforms do not yield representative samples. Platform demographics are
skewed, coordinated activity occurs, and those who do not participate are not
observed. Sentira does not state what share of a population holds a view, and
cannot. It states that a subject rose at a given time and carried a given tone.
The defensibility of the product rests on this distinction.

### Not an instrument for tracking individuals

Sentira does not produce individual-level stance profiles. This is a deliberate
architectural requirement. The offline subset implements identifier and target
validation; the remaining production controls are planned:

- Author identifiers are hashed at the collector boundary using HMAC-SHA256; no
  later stage of the system sees a raw identifier
- The platform name is part of the hash input, so the same input identifier hashes differently across platforms; this
  does not prevent linkage through content
- The storage schema carries no raw-identifier column, and a test asserts this
  against the schema itself
- Stance targets are restricted to political parties, state institutions and
  formally declared candidates. Journalists, academics, local critics and private
  individuals cannot be defined as targets; the schema rejects them at load

The last constraint is the one most easily overlooked. Hashing authors alone is
insufficient: if the target side were unrestricted, tone toward a named individual
over time could be reconstructed from a hashed corpus — precisely the capability
the system is designed not to have. The two constraints operate together, not
separately.

## 3. Position in the field

Two product shapes share this category. The distance between them is legal and
ethical rather than technical.

| | **Social listening** | **Entity resolution** |
|---|---|---|
| Question | How did tone on this subject move? | What is known about this person? |
| Output | Aggregate time series | Person or entity dossier |
| Examples | Brandwatch, Zignal Labs, Graphika | Palantir Gotham |
| Personal-data exposure | Manageable by design | Special-category data at individual level |
| **Sentira** | **Here** | Out of scope |

What makes entity-resolution platforms contested is not their technology but their
capacity to assemble individual-level dossiers. Sentira excludes person-level reporting from its product contract. Persistent
hashes still permit internal within-source linkage and must not be described as
anonymity.

### Differentiation

Established vendors process far greater volume. The advantage claimed is not scale:

1. **Language-specific processing.** The pipeline is built for one language at a
   time — its morphology, non-standard orthography, emoji use and informal register
   — rather than relying on a multilingual default.
2. **Local operation.** Models run on the operator's hardware and content does not
   leave it. This is an operating choice; exclusive market differentiation is not established.
3. **Privacy by construction.** Aggregate-only measurement and identity hashing are
   the architecture itself, not a compliance layer added afterwards.

### Applicability

The product is deliberately not bound to one client or one event. Differences
between applications reduce to two configuration files, `targets.yaml` and
`topics.yaml`; collection, language processing and scoring are unchanged. The
product is therefore not named after any client: an engagement ends, the product
remains. Application areas are listed in the [README](../README.md#applicability).

## 4. Out of scope regardless of request

The following are excluded even where a client asks for them, and are stated in
writing before any engagement:

- Stance tracking or listing of specific individuals — journalists, academics,
  critics or ordinary users
- Person-level reporting, "who said what" queries, or account dossiers
- Delivery of user identifiers to a client
- Collection that breaches platform terms
- Output represented as a representative measure of population opinion

These are not negotiable. Both legal exposure and the defensibility of the product
depend on them.

## 5. Open items

Items that must be closed before any figure is represented to a client:

1. **No live collection run.** Collection volume is currently *calculated*, not
   *measured*. One authenticated run converts it to a measurement.
2. **Accuracy is not measured.** Sentiment and stance macro-F1 follow the gold
   standard. Every F1 is reported beside a majority-class baseline; an accuracy
   claim without its baseline does not survive the first meeting.
3. **Lawful basis for processing.** Local inference avoids sending content to a hosted inference service.
   It does not establish a lawful basis: classifying political opinion is processing
   of special-category data wherever the hardware sits. The data-protection
   authority's published guidance on election-related processing does not address
   opinion research, nor public availability of data as a basis; any basis must
   therefore be built from the statute and from the authority's decisions.
   Qualified legal advice will be obtained. The claim "processing is local,
   therefore compliant" will not be made.
4. **Electoral-law restrictions.** Electoral law in the operating jurisdiction
   prohibits the publication and "distribution in any form" of opinion research
   during a pre-election window, and requires disclosure of the funder whenever
   results are published. Whether an unpublished deliverable to a single client
   constitutes distribution is not answered by the statutory text. Referred to
   counsel.
5. **Name clearance.** The name has been checked by web search only. Trademark
   register searches are required before commercial use.
