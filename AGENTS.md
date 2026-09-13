# Working agreement

Instructions for any agent or contributor working in this repository.

## What this repository is

Sentira measures public discourse at the aggregate level. The repository contains
design documentation and an **offline foundation for synthetic data only**.
Production collection, lifecycle controls and forecasting are not implemented.
Read docs/CONTINUATION.md for the exact tested subset.

Read in this order before changing anything:

1. [README](README.md) — what the system produces and what it refuses to do
2. [docs/CONCEPT.md](docs/CONCEPT.md) — definition, boundaries, open items
3. [docs/ROADMAP.md](docs/ROADMAP.md) — approved design sections, validation criteria
4. [docs/BACKTEST.md](docs/BACKTEST.md) — evaluation protocol and the first phase

## Constraints that are not open for negotiation

These are binding architectural requirements. Implemented guarantees require
named tests; future requirements must not be presented as implemented behaviour.
Do not relax one because it is inconvenient; raise it instead.

- **Aggregate only.** No individual-level output, no person-level query, no account
  dossier. Not a configuration flag — the schema has no place to put one.
- **Identity is hashed at the collector boundary**, HMAC-SHA256 with the platform
  name in the input. No raw identifier may reach storage; tests assert this against
  the schema and against the emitted objects.
- **Stance targets are restricted** by schema to parties, state institutions and
  formally declared candidates. Hashing authors alone would be insufficient: an
  unrestricted target side would let tone toward a named individual be
  reconstructed from a hashed corpus.
- **Cumulative counters live only in the snapshot table**, never on a document.
- **Point-in-time correctness** follows the replay rule of
  [BACKTEST.md](docs/BACKTEST.md): a retrieved row is visible at *T* only where the
  registered collection policy would have retrieved it by *T*. One read path, and
  an invariance test that asserts it.
- **Official APIs only.** No scraping, no endpoint outside the registered set, and
  the quota ledger is debited before each call.
- **Local inference.** No content is sent to a hosted inference service.

## Evidence discipline

Every figure carries how it was obtained: *calculated* (arithmetic), *measured*
(observed directly), or *verified* (confirmed against a primary source). Presenting
a calculation as a measurement is the failure mode this project is built to avoid.

- Accuracy figures are reported beside a majority-class and a random baseline. A
  figure without its baseline is not reported.
- A negative result is a finding. Report it, do not bury it or soften it.
- When a source cannot be reached, write that it could not be reached. A gap is
  worth more than a plausible invention — this applies with particular force to
  citations: no reference is cited unless its text was actually retrieved.

## Writing style

Clean academic English, British spelling (*normalise*, *licence* as a noun). Short
paragraphs, tables over prose, no marketing register.

Documentation is written in **generic terms**: the operating jurisdiction and the
target language are described by role, never named, and neither are clients. Keep
it that way in every file, including commit messages.

## Repository hygiene

- Internal research material lives outside this repository and stays there. It is
  listed in `.gitignore`; do not commit it, quote it at length, or link to local
  paths from published documents.
- Secrets come from the environment. `.env` is never committed; `.env.example`
  documents the variables.
- Commit messages are in English, imperative mood, and explain why rather than
  what. They carry no co-author or generated-by trailers.
- Before committing documentation, check that no jurisdiction-specific or
  language-specific term has crept in.

## When implementation begins

- Python 3.12. Small, focused modules; the module tree in the README is the map.
- **Every guarantee above maps to a named test.** A guarantee without a test is a
  sentence, not a property. The current mapping is the table at the end of
  [BACKTEST.md](docs/BACKTEST.md).
- Definitions, thresholds and matching rules are locked and hashed *before* any
  counting or evaluation runs against them. The evaluation refuses to run against a
  modified registration.
- No test touches the network. Foundation fixtures are explicitly synthetic;
  future source-adapter fixtures must be sanitised recorded responses and kept
  distinguishable from synthetic data.

## State of play

The approved first implementation is an offline synthetic-data foundation.
The first phase
counts how many surges the available history contains — it exists to establish
early, rather than late, whether a retrospective evaluation is possible at all.
Live collection is blocked on source-use acceptance, lifecycle implementation
and credentials. These do not block offline development. The approved amendment
is docs/IMPLEMENTATION_START.md; current results are in docs/CONTINUATION.md.
