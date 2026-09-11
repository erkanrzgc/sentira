# Feasibility findings

Each figure states how it was obtained: *calculated* (arithmetic), *measured*
(wall-clock timing or a live call), or *verified* (confirmed against a primary
source). The distinction matters in practice — a calculation presented as a
measurement fails at the first question.

Last updated: 2026-09-11

---

## 1. Collection volume and cost

### Video-platform commentary — *calculated*, not yet measured

| Profile | Quota units | Comment ceiling |
|---|---|---|
| 60 channels × 10 videos/day × 3 pages | 1,860 | 180,000/day |
| Free daily quota | 10,000 | — |
| Utilisation | **19%** | — |

At expected fill rates this corresponds to roughly 1.5–3 million comments per month
(*calculated*).

**This profile is superseded for measurement purposes.** It reads each video once,
which is adequate for volume but not for evaluation: comments arriving after that
single read are never observed, so the profile cannot serve as the control group for
historical retrieval, cannot yield a collection-latency figure, and cannot produce a
prospective test set. The registered policy polls each video at several ages
([BACKTEST.md](BACKTEST.md#03-the-replay-rule)), which raises the cost and divides
the quota into enforced reservations:

| Reservation | Units/day | Basis |
|---|---|---|
| Live collection under the registered policy | 6,000 | 600 new videos/day × 6 polls, plus discovery, plus paging for new threads |
| Historical retrieval | 3,000 | The remainder |
| Survival sampling | 500 | Re-retrieval of complete strata at three lags |
| Buffer | 500 | Retries and overrun |

Three inputs remain unmeasured — videos per channel-day, threads per video, and the
realised cost of the policy — so the table is *calculated* and is re-costed against
the first live run before it is locked. The consequence is stated plainly in the
backtest design: historical depth is bought out of 3,000 units a day, so a year of
history would take roughly 220 days of retrieval, and whether a retrospective
evaluation is possible at all is the first question the work answers.

**Quota arithmetic** — the most consequential engineering detail in collection:

| Call | Units | Use |
|---|---|---|
| `search.list` | **100** | Not used — exhausts the daily quota in 100 calls |
| `playlistItems.list` | 1 | Video discovery (50 videos per page) |
| `commentThreads.list` | 1 | Comment retrieval (100 comments per page) |
| `channels.list` | 1 | Not needed — see below |

A channel's uploads-playlist identifier is its channel identifier with the second
character replaced by `U` (`UC…` → `UU…`). This derivation removes one unit per
channel. Discovery by enumerating the upload playlists of a curated channel list,
rather than by search, yields 50–100 times more data for the same quota.

> **This is a calculation, not a measurement.** No authenticated call has been made.
> To convert it: obtain an API key, resolve channel handles, perform one full run,
> and compare units spent against the estimate. The figure from that run is the one
> to report.

Data cost: **$0 per month** within the free quota; commercial use is permitted and
no audit is required at this volume.

### Platform access — *verified* 2026-09-02 against primary sources

| Platform | Status | Note |
|---|---|---|
| **YouTube** | Backbone | 10,000 units/day free; commercial use permitted |
| **X** | Optional | Pay-per-use at $0.005 per read, 2M/month cap; 400k posts ≈ $2,000/month |
| **Reddit** | Out of scope | Free tier prohibits commercial use; commercial plans from ≈ $12,000/month |
| **Instagram / TikTok** | Out of scope | No official comment-reading API; scraping breaches terms |

Open protocols (Bluesky, Mastodon) are not assessed in this record.

### News feeds — *measured* 2026-09-11

A sample of twelve national news outlets in the target language, chosen to span the
editorial spectrum, was probed with live HTTP requests:

| Measure | Result |
|---|---|
| Outlets with a working feed | **11 of 12** |
| Publication timestamp (`pubDate`) | Present in all 11 |
| Full text (`content:encoded`) | Absent in all 11 — title and summary only |
| Historical depth | Current feed window only |
| `robots.txt` disallowing AI crawlers by name | 4 of 12 |

Two consequences follow. First, news contributes *agenda events* — what appeared,
when, and where — and not tone; tone continues to come from authored commentary.
The two source kinds do different work, which determines the fusion design (see
[ROADMAP.md](ROADMAP.md#section-2--document-model-and-source-fusion)).

Second, a feed is the publisher's own declared distribution channel and `robots.txt`
directives address crawlers, so the disallow entries do not technically bar feed
retrieval. They are nonetheless a clear statement of publisher intent. Sentira does
not train models on news text; it derives an agenda signal from title, date and
source. That distinction must be written into the methodology note and into
contracts. The rights position of aggregating title, summary and link is referred to
counsel.

Because a feed carries only its current window, feed-derived series are
forward-only from the first day of collection: an unpolled window is lost
permanently, which is why collection begins before any series is built.

### Global event database (GDELT DOC 2.0 API) — *measured* 2026-09-11

| Measure | Result |
|---|---|
| Query by source country, 7 days, 100 records | 100 of 100 returned; 95 in the target language |
| Text encoding | Corrupted: characters outside Latin-1 mis-decoded, some dropped entirely |
| Rate limiting | HTTP 429 on 4 of 5 queries despite 15-second spacing |

The corruption is not recoverable where characters were dropped. GDELT is therefore
usable as a metadata signal but not as a text source for tone analysis. The DOC API
suits exploration only. The raw export and mentions archive runs to roughly 13 GB
per year (*calculated*, extrapolated from a single 15-minute slice); it is not a
series source, and is used offline as a candidate generator for the human-curated
event log ([BACKTEST.md](BACKTEST.md#a10-ground-truth-event-log)).

---

## 2. Local model throughput — *measured*

Hardware: NVIDIA RTX 5060 Laptop (Blackwell, sm_120, 8 GB VRAM) · Ryzen 9 8945HX ·
47 GB RAM. Method: the production stance prompt, single stream, no batching,
reasoning disabled, wall-clock timing.

| Model | docs/s | Median | 100k docs | 2M docs (monthly) | Format compliance |
|---|---|---|---|---|---|
| **qwen3:8b** (q4) | **3.30** | 304 ms | **8.4 h** | 168 h | **40/40** |
| qwen3:4b (q4) | 3.21 | 308 ms | 8.6 h | 173 h | 0/40 |
| 8B domain fine-tune | 1.41 | 709 ms | 19.7 h | 394 h | 30/30 |
| 4B domain fine-tune | 2.26 | 386 ms | 12.3 h | 245 h | 0/30 |

### Consequence: distillation is required

Two million documents per month would take 168 hours. A large language model cannot
sit in the production path. It is used only as a **teacher**: it labels a silver
set, a ~110M-parameter encoder is trained on that set, and the encoder runs in
production. Model selection is recorded in [MODELS.md](MODELS.md).

### What the measurement changed

Labelling proved about 2.3 times cheaper than first estimated; the initial
measurement had been taken on a slower domain fine-tune. One hundred thousand
examples can be labelled overnight, so the silver set need not be capped at
5,000–10,000 examples — 50,000–100,000 is feasible, which bears directly on student
quality.

### Teacher choice: qwen3:8b

The only argument for the 4B model would be speed, and there is none (3.21 against
3.30 docs/s). The 4B model spent its entire 8-token output budget on malformed
output, while the 8B model produced a valid label in 3.7 tokens on average. The
smaller model is faster per token but not per task.

*Recorded caveat:* prompts were sent as raw completions through `/api/generate`,
without the chat template. The 4B model's format failures may be partly due to this
and might resolve through `/api/chat`. Even so, with no speed advantage there is no
reason to pursue it.

### Open item: class balance

Across the 40-item measurement, the teacher never produced `unrelated` (30 against,
10 favour). This may be reasonable for a sample weighted toward critical political
commentary, but **class imbalance in the teacher transfers directly to the
student** and aggravates the majority-class baseline problem. The teacher's class
distribution will be measured separately against the gold standard.

*Available lever:* the measurement is single-stream. Batching through
`OLLAMA_NUM_PARALLEL` may yield a further two- to four-fold gain; not yet measured.

---

## 3. Setup pitfalls — *measured*

| Item | Finding |
|---|---|
| GPU | Blackwell sm_120. The default PyTorch wheel does not run; a CUDA 12.8+ build is required (`--index-url https://download.pytorch.org/whl/cu128`) |
| Python | The machine default, 3.14, is ahead of the ML stack and lacks wheels. **3.12** is used |
| Ollama | 0.30.0 installed and working; qwen3:8b and qwen3:4b pulled |
| Model download | ≈ 1.4 MB/s measured; a 5 GB model takes about an hour |

---

## 4. Accuracy — *not yet measured*

Accuracy follows construction of the gold standard. Acceptance thresholds: sentiment
≥ 0.75 and stance ≥ 0.65 macro-F1, **and each must exceed its own majority-class
baseline by a meaningful margin.**

The baseline is mandatory because the real-world distribution of three-class stance
is skewed: a classifier that always answers `unrelated` can already score well. An
F1 figure without its baseline is not reported.

**Annotation consistency.** The project has a single annotator, so a two-annotator
Cohen's kappa cannot be produced, and presenting one as if it had been would be
unacceptable in a client-facing document. Instead, a held-out subset of 100 items is
re-labelled blind at least one week after the first pass, and intra-annotator
agreement is reported — named as such, not as inter-annotator agreement.

---

## 5. Data protection

Enforced in code:

- Author identifiers hashed with HMAC-SHA256 at the collector boundary
- Platform name included in the hash input, preventing cross-platform linkage
- No raw-identifier column in the schema, asserted in test
- Stance targets restricted to parties, institutions and declared candidates,
  asserted in test
- All models local, which removes the cross-border transfer item

**Open item.** Local operation resolves one item, not the question as a whole. The
lawful basis for processing political opinion is recorded in
[CONCEPT.md](CONCEPT.md#5-open-items) as requiring qualified legal advice.
