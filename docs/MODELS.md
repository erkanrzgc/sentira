# Models and licensing

The architecture labels data with a large language model, distils the result into
a small encoder, and ships the encoder inside a commercial product. The relevant
question is therefore not *may this model be run commercially* but *may a student
trained on its outputs be sold*. The two questions engage different licence clauses
and receive different answers. **Teacher selection is consequently governed by
licence before quality.**

**Status.** Licence fields, gating and parameter counts were verified against raw
Hugging Face Hub API data (`cardData.license`, `gated`, `safetensors.total`) for 29
repositories on 2026-09-10; the per-repository table is held with the underlying
research material. Readings at the level of individual clauses are marked where not
yet verified. Nothing here is legal advice.

---

## 1. Licence inheritance through distillation

| Family | Licence | Training another model on outputs | Inherited by the student | Gated |
|---|---|---|---|---|
| Qwen3 (8B, 4B) | `apache-2.0` | Permitted | **No** | No |
| Llama 3.0 (`llama3`) | Meta Llama 3 Community | §1.b.v prohibits using outputs "to improve any other large language model" | **Prohibited, or a grey area** | — |
| Llama 3.1 | Meta Llama 3.1 Community | §1.b.i permits it, but a distributed derivative's name must begin with "Llama" | Naming constraint | `manual` |
| Gemma 2–3 | Gemma Terms of Use | §1.1(e) names distillation as a Model Derivative; §3.1 requires use restrictions to be passed down by contract | **Yes, chained** | `manual` |

Three practical consequences:

**(a) Language-adapted models inherit their base licence.** Several prominent
language-adapted LLMs are continued-pretraining derivatives of Llama 3.0 and carry
`llama3`, not the 3.1 licence; this was confirmed from the `base_model` declared on
their model cards, not only from the licence tag. The relaxed 3.1 clause does not
apply to them. Whether a ~110M-parameter encoder classifier falls outside the term
"large language model" is a genuine legal grey area that cannot be settled
technically. The risk-free path is not to use this family as a teacher.

**(b) Gemma derivatives impose chained obligations.** Distillation is named in the
terms, and use restrictions must be embedded in the sale contract and notified to
downstream users. This is not a prohibition, but it is a contractual burden.

**(c) A gated repository is a signature.** Downloading weights from a `manual`-gated
repository requires click-through acceptance on the organisation's behalf. Qwen3 is
not gated.

*Not yet verified at clause level:* the full text of Llama 3 §1.b.v and whether it
reaches an encoder classifier (a legal question); the chaining provisions of Gemma
§1.1(e) and §3.1.

## 2. Licence hazards

- **Non-commercial licences.** Models under `cc-by-nc-sa-4.0` cannot be used in a
  commercial product; ShareAlike additionally requires derivatives to carry the same
  licence, which is incompatible with a closed product. A licence tag of `other`
  requires reading the card: one surveyed model is restricted to non-commercial
  academic research. Such models are frequently cited in the academic literature and
  must not leak into proposals.
- **An empty licence field grants nothing.** In one surveyed family, only the
  smallest size declared MIT; the licence field of the remaining sizes was empty.
  An absent licence is not a permission — without a grant of rights there is no
  right of use. Written permission, or an alternative, is required.
- **Popularity is not permission.** Download counts provide no legal cover.

---

## 3. Selection

### Teacher

**Qwen3-8B (`apache-2.0`).** Measured at 3.30 documents per second with 40/40 format
compliance on this hardware ([FEASIBILITY.md](FEASIBILITY.md#2-local-model-throughput--measured)).

**Candidate:** a language-adapted 7B model released under `apache-2.0` — continued
pretraining on Qwen2.5-7B according to its model card (the card's description of the
training data is not yet independently verified). Because both candidates are
Apache-2.0, trying both and choosing on measured labelling quality costs nothing in
licence terms — a freedom not available within the Llama or Gemma families.

### Student

**A cased monolingual ConvBERT encoder, 106,816,136 parameters, MIT licence,**
pretrained on the target-language portion of mC4 (242 GB according to its model
card). The reasons:

1. **Cased.** Stance targets are parties, institutions and declared candidates —
   proper nouns. Case carries information. The uncased alternatives also require
   language-specific case-mapping workarounds before tokenisation, which lose
   information and add fragility.
2. **Domain.** Pretraining on web text places it closer to informal written
   language than encoders trained predominantly on encyclopaedic and parallel
   corpora.
3. **Clean chain.** An MIT student with an Apache-2.0 teacher is the combination
   with no inheritance obligation at any stage. The product can be sold under any
   name and licence.

**If speed is needed:** a 68M-parameter distilled cased encoder from the same
publisher, also MIT — roughly 40% smaller.

**Caveat.** None of these encoders was pretrained on social-media text.
Abbreviation, emoji, vowel dropping and irregular syntax produce domain shift. The
expected remedy is a round of domain-adaptive pretraining (masked language
modelling) on the project's own unlabelled data *before* distillation; at 107M
parameters this fits comfortably in 8 GB. An uncased RoBERTa model pretrained on
social-media text (MIT) is far ahead on domain match and serves as a comparison
benchmark rather than as the student.

**Topic clustering** is a separate task from classification. An MIT-licensed
560M-parameter embedding model derived from `intfloat/multilingual-e5-large-instruct`
is available for it, with a clean licence chain.

---

## 4. What fits in 8 GB of video memory

Rule of thumb: **weight size ≈ parameters × bits ÷ 8**, with Q4_K_M at about 4.5
bits per parameter in practice. The desktop already holds 0.5–1 GB, leaving roughly
7–7.5 GB, before the KV cache, which grows linearly with context length.

| Model | Q4_K_M weights | In 8 GB |
|---|---|---|
| 2B | ≈ 1.2 GB | Very comfortable; even fp16 (≈ 4.1 GB) fits |
| Qwen3-4B | ≈ 2.3 GB | Comfortable, room for long context |
| 7B | ≈ 4.3 GB | Fits, moderate context |
| Qwen3-8B | ≈ 4.6 GB | Fits; KV cache tight at long context |
| 9B | ≈ 5.2 GB | Tight, short context |
| Gemma-3-12B | ≈ 6.9 GB | **No room for the KV cache — does not fit in practice** |
| Encoders (68–185M) | fp16 ≈ 0.14–0.37 GB | Full fine-tuning possible |

These sizes are *calculated* (parameters × 4.5 ÷ 8), not measured from real GGUF
files; expect deviations of around ±10%.

With 47 GB of system memory, partial CPU offload through `llama.cpp` is a real
alternative: 12B models run, at a substantial cost in tokens per second. Labelling is
an offline batch job, so the trade is acceptable.

## 5. Toolchain risk

The GPU is Blackwell (compute capability sm_120), and "the model fits" is not the
same as "the stack runs". The PyTorch 2.7 release announcement lists Blackwell
support under the heading **"[Prototype]"**, and describes the CUDA 12.8 wheels as
available "across Linux x86 and arm64 architectures" — Windows does not appear in
that sentence. Installation must target a CUDA 12.8+ index rather than the default.

Status: the Ollama path is *measured* working on this machine. PyTorch, 4-bit
quantisation (bitsandbytes) and vLLM on Windows with sm_120 are **not yet
benchmarked**. Demonstrating that stack end to end on the target machine is the
first technical task, ahead of model selection; the `llama.cpp`/GGUF route depends
less on the CUDA stack and is the fallback.

## 6. Not yet measured

- Labelling quality of the teacher candidates against the gold standard
- Target-language benchmark scores for any candidate
- The teacher's class distribution against the gold standard
  ([FEASIBILITY.md](FEASIBILITY.md#open-item-class-balance))
