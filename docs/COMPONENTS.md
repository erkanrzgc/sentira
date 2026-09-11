# Reusable open-source components

**Status: unverified survey.** Compiled on 2026-09-09 from GitHub API, PyPI JSON API
and Hugging Face Hub API responses. The adversarial verification pass did not run.
Star counts, dates and versions are snapshots and will drift. Licence readings are
not legal advice. Nothing here enters client material without re-verification.

Tables give the date of the last commit rather than GitHub's `pushed_at`, which
proved misleading — a thirteen-month discrepancy in one case.

---

## Licence hazards — read first

A commercial product is at stake, so licence matters more than popularity.

| Component | Licence | Decision for a commercial product |
|---|---|---|
| The most visible NLP toolkit for the target language | **AGPL-3.0** | **Do not use.** Offered as a service, network use triggers source disclosure for the whole product |
| `jinaai/jina-embeddings-v3` | **CC-BY-NC-4.0** | **Do not use.** Non-commercial |
| The most downloaded sentiment model for the target language | **None** | **Do not use.** No licence means no right of use, whatever the download count |
| `grafana/grafana` | AGPL-3.0 | Usable as a separate, unmodified process; embedding or forking is risky |
| `metabase/metabase` | AGPL + Metabase Commercial | The `enterprise/` directory is commercially licensed; a separate `LICENSE-EMBEDDING.txt` governs embedding |
| `davidjurgens/potato` | GPL-3.0 | Acceptable as a separate internal tool; cannot be embedded |

Apache-2.0 and MIT components are unrestricted. **Consequence:** the two most visible
language-specific resources cannot be used commercially. This removes the "download
a ready sentiment model" route and makes training on the project's own labelled data
mandatory.

---

## Few-shot classification: SetFit

SetFit is actively maintained, contrary to its reputation during 2025.

| Measure | Value |
|---|---|
| Repository | `huggingface/setfit` |
| Licence | Apache-2.0 |
| Stars | 2,799 |
| Last commit | 2026-09-04 |
| Latest release | v1.2.0, 2026-09-04 |
| Python | ≥ 3.9 (3.13 officially supported from v1.2.0) |

The v1.2.0 release notes add compatibility with `transformers` v5,
`sentence-transformers` v6, `huggingface_hub` v1 and `datasets` v5.

**How many examples suffice?** Source: Tunstall et al., *Efficient Few-Shot
Learning Without Prompts*, arXiv:2209.11055 (2022). The main experiments use N = 8
and N = 64 labelled examples per class. The multilingual experiment uses the
Multilingual Amazon Reviews Corpus in six languages, in three settings: `each`
(train per language), `en` (train on English only), `all` (train on all). At N = 8,
mean absolute error × 100 (lower is better), over ten random splits:

| Setting | SetFit | Fine-tuning |
|---|---|---|
| `each` | **82.9 ± 4.3** | 122.9 ± 14.0 |
| `en` | **82.6 ± 4.8** | 115.9 ± 11.3 |
| `all` | **83.0 ± 5.3** | 117.8 ± 4.9 |

**The target language is not among the six.** No verified figure supports "eight
examples per class suffice" for it. The spread between settings (82.6–83.0) is far
smaller than the standard deviations, so **no conclusion about cross-lingual transfer
can be drawn from this table**; SetFit's advantage over fine-tuning, by contrast, lies
well outside the deviations and is real.

**Planning consequence.** Pilot with eight examples per class, but budget for
**50–100 per class** — an engineering estimate, not a measurement — and measure on a
target-language test set. Agenda and tone labels are more subjective than star
ratings; in-domain validation is required.

Body candidates:

| Model | Licence | Note |
|---|---|---|
| A target-language BERT-base fine-tuned on NLI and STS | Apache-2.0 | ~110M, actively updated; first choice |
| `intfloat/multilingual-e5-base` | MIT | Multilingual |
| `BAAI/bge-m3` | MIT | Multilingual |

**Video memory (not measured).** SetFit's cost centre is contrastive pair
generation, which scales with the `num_iterations` parameter — a tunable budget
rather than unavoidable quadratic growth. A 110M body with a small batch should fit
in 8 GB; this is not to be committed to without measuring at the intended N.

**CPU inference hedge.** `MinishLab/model2vec` (MIT; release 0.9.0, 2026-08-12)
distils a sentence-transformer into static embeddings. The ready model
`minishlab/potion-multilingual-128M` is distilled from `BAAI/bge-m3`, covers 101
languages at 256 dimensions under MIT, and reports 90.86% of LaBSE's performance at
orders-of-magnitude higher speed. Its training corpus includes the target language
(confirmed through the corpus language tags), but no target-language quality score
is published.

**Architectural consequence.** Train with SetFit for label efficiency, then distil
with model2vec and run inference on CPU — the GPU for training, the CPU for
inference. This is an alternative to the teacher–student route in
[MODELS.md](MODELS.md); both are to be compared on the same gold standard.

---

## Collection: the official API is the only clean route

| Tool | Licence | Terms of service |
|---|---|---|
| `googleapis/google-api-python-client` | Apache-2.0 | **Clean** — official API |
| `egbertbouman/youtube-comment-downloader` | MIT | Scraping — terms risk |
| `yt-dlp/yt-dlp` | Unlicense | Scraping — terms risk |

The latter two are maintained and permissively licensed, but they breach platform
terms and are excluded by project constraint.

Quota (official documentation, 2026-09-09): `commentThreads.list` costs 1 unit with
`maxResults` up to 100; the default project quota is 10,000 units per day. The survey
reports that `search.list` now draws on a separate bucket capped at 100 calls per
day; either way, **video discovery, not comment retrieval, is the bottleneck**, which
confirms enumerating curated channels' upload playlists. To be confirmed with a single
live call.

## Social-listening frameworks: a negative finding

No maintained, permissively licensed social-listening skeleton worth adopting was
found. The most serious candidate, `obsei/obsei` (Apache-2.0), last received a commit
on 2024-10-04 and a release on 2023-12-31. The remainder were abandoned between 2013
and 2019 or are coursework projects. The orchestration layer — collection, queue,
language processing, storage, presentation — is written in-house. The search was
limited to four terms and the leading results.

## Topic detection, annotation and morphology

| Project | Licence | Role |
|---|---|---|
| `MaartenGr/BERTopic` | MIT | **Agenda detection** — unsupervised topic clustering; produces clusters, not individuals, consistent with the aggregate-only design |
| `MaartenGr/KeyBERT` | MIT | Key-term extraction |
| `HumanSignal/label-studio` | Apache-2.0 | **Annotation** — the healthiest option |
| `doccano/doccano` | MIT | Lightweight annotation; activity has slowed |
| `argilla-io/argilla` | Apache-2.0 | **In maintenance mode — do not select** |

Argilla's README states that the original authors have moved on, no new features
will be added and only bug fixes will be made. It should not underpin a commercial
product.

A mature morphological analyser for the target language exists under Apache-2.0,
although the GitHub API reports its licence as `NOASSERTION`; the licence file itself
is Apache-2.0. It is written in Java and would connect to the Python pipeline through
JPype or a service; the integration cost has not been assessed.

## Presentation layer

`apache/superset` (Apache-2.0), `streamlit/streamlit` (Apache-2.0), `plotly/dash`
(MIT) and `duckdb/duckdb` (MIT) are all commercially usable and actively maintained.
Grafana (AGPL-3.0) and Metabase (AGPL plus commercial) require legal review in an
embedding scenario. Streamlit suits a quick internal panel; Superset suits a
multi-tenant panel offered to clients.
