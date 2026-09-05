# Fine-Tuning Design Report — Survey Sentiment/Topic Classification

**Scenario** (as posed in the assessment): omniSense processes 10,000
free-text survey responses per day and needs to classify each into one of
8 sentiment+topic categories (e.g. *Positive – Food Quality*, *Negative –
Wait Time*, *Neutral – Staff*). GPT-4o does this accurately today but at a
cost that doesn't scale to that volume. This report is the full engineering
version of the answer condensed to 421 words in `README.md` §9 — same
conclusions, with the reasoning and trade-offs spelled out.

This is a **design document**: no training has actually been run for this
task. Everything below is a proposed approach, distinguished from the
implemented MiniSense codebase (agents, RAG, dataset generator), which
*is* built and tested.

---

## 1. Framing the problem correctly first

Before choosing a model or technique, it's worth being precise about what
kind of problem this is, because that choice drives everything downstream:

- **8-way single-label classification**, not generation. The output space
  is small and fixed. This rules out needing a large generative model —
  the task doesn't require the model to *write* anything, only to pick one
  of 8 labels.
- **Domain-narrow vocabulary.** Survey free-text about food/wait-time/staff
  at a restaurant chain uses a much smaller, more repetitive vocabulary
  than open-domain text. This matters for how much data is actually needed
  (§2) and how aggressively the base model can be shrunk (§3).
- **The frontier model's outputs are the closest thing to ground truth
  available at the start.** There's no pre-existing human-labeled dataset
  for this exact taxonomy — GPT-4o's own classifications are the initial
  supervision signal, which shapes the whole data strategy in §2.

---

## 2. Data strategy

### 2.1 Bootstrapping labels

Start by running the frontier model (GPT-4o) over a **stratified sample**
of historical survey responses — stratified by:
- `business_id` / location (different locations may skew toward different
  complaint types, per MiniSense's own dataset design — see
  `data/generate_data.py`'s per-location `quality_bias`)
- `rating` (1–5, so all sentiment bands are represented, not just the
  common ones)
- `response_channel` (mobile/web/kiosk text can differ stylistically)
- Time period (captures any seasonal/drift effects)

This gives cheap initial labels across the full space of the 8 categories,
including rare ones, rather than a random sample that would badly
under-represent minority classes (e.g. *Positive – Wait Time* is
presumably far rarer than *Negative – Wait Time*).

### 2.2 Human quality control — non-negotiable

**Never ship 100% frontier-labeled data with zero human review.** The risk
is subtle and serious: any systematic bias or blind spot in GPT-4o's
labeling (ambiguous mixed-sentiment text, sarcasm, category boundary
confusion between e.g. *Negative – Food Quality* vs *Negative – Staff* when
a review blames "the kitchen staff") gets distilled directly into the
fine-tuned model, with no independent check. The fix:
- Human reviewers audit a **stratified subset** (not random — oversample
  the cases the frontier model itself reports low confidence on, and cases
  near category boundaries).
- Disagreements between the frontier label and human judgment become the
  **highest-value training examples** — they mark exactly where the
  category boundaries are ambiguous, which is precisely what the
  fine-tuned model most needs to learn correctly.
- Track inter-rater agreement (human vs. frontier, and human vs. human on
  a double-annotated slice) to get an empirical estimate of how "hard" this
  task actually is — this number also becomes a ceiling on what the
  fine-tuned model can realistically achieve.

### 2.3 Dataset size estimate

**Target: ~3,000–5,000 labeled examples for a first pass.**

Reasoning, not a guess pulled from a table:
- 8-way classification with a narrow, domain-specific vocabulary is a much
  easier learning problem than open-ended generation or broad-domain
  classification. Rule-of-thumb guidance for fine-tuning a classifier head
  (or a small-model instruction-following classifier) on a well-separated
  label space is on the order of a few hundred examples *per class* —
  8 classes × ~400–600 examples/class ≈ 3,200–4,800.
- This is a **starting point to validate against real eval numbers**, not
  a number frozen in advance. If per-class F1 (§4) shows specific
  categories underperforming after the first training run, the next round
  targets *those* categories specifically via active sampling (§2.4)
  rather than uniformly growing the whole dataset.

### 2.4 Active learning for round 2+

Rather than randomly growing the labeled set, prioritize for human
labeling:
1. **Low-confidence predictions** from the first fine-tuned checkpoint
   (near-uniform softmax over the 8 classes).
2. **Disagreement cases** between the fine-tuned model and the frontier
   model on new unlabeled data.
3. **Under-represented categories** flagged by the per-class F1 breakdown.

This targets labeling effort at the examples that actually move accuracy,
instead of paying for more of what the model already handles well.

### 2.5 Class imbalance

Deliberately **oversample rare categories** (both in the initial curated
set and via targeted round-2 collection) so that real-world class
imbalance — some complaint types are just rarer than others — doesn't get
baked into the classifier as "just predict the majority class when
uncertain." This is also why **macro F1**, not accuracy, is the primary
eval metric (§4): macro-averaging weights every class equally regardless
of its frequency, so a model that's excellent on common categories but
useless on rare ones gets penalized correctly.

### 2.6 Splits and leakage prevention

- **Train / validation / test**, roughly 70/15/15, stratified by category
  so every class appears proportionally in each split.
- **Group-aware splitting**: if any responses are near-duplicates of each
  other (a common artifact when many customers write similar short
  complaints — "wait was too long", "waited forever"), split at the level
  of near-duplicate clusters, not individual rows, so the same phrasing
  doesn't leak across train and test and inflate the reported score.
- The **test set is frozen** the moment it's created and never used to
  make any training or hyperparameter decision — only for the final
  go/no-go evaluation in §4.

---

## 3. Model & technique selection

### 3.1 Base model

**A small open instruction-tuned model in the 3B–8B parameter range**
(e.g. Llama 3.1 8B, or a comparably sized instruct model). Reasoning:

| Consideration | Why 3B–8B is the right range here |
|---|---|
| Task complexity | 8-way classification over domain-narrow text doesn't need a large model's broad world knowledge or long-context reasoning |
| Inference cost/latency | At 10,000 requests/day, a small model keeps per-request cost and latency low enough to run economically, including on modest GPU hardware |
| Deployment footprint | Fits on a single consumer/prosumer GPU quantized, unlike a 70B+ model |
| Context length | Survey free-text responses are short (a sentence or two); no need for the long-context capability that larger models are partly built for |

A larger model (30B+) would not meaningfully improve accuracy on a task
this narrow and would multiply serving cost for no benefit — the opposite
mistake from the one this whole project is trying to fix (an expensive
model for a task that doesn't need one).

### 3.2 LoRA vs. QLoRA vs. Full Fine-Tuning

| Approach | Verdict | Why |
|---|---|---|
| **Full fine-tuning** | Rejected | Updates every parameter — justified only when the base model's domain vocabulary is badly mismatched from the target domain. Restaurant/retail survey text is well within the training distribution of any modern open instruct model; there's no vocabulary gap to close. Also far more expensive in compute/memory and risks catastrophic forgetting of the base model's general instruction-following ability, which isn't needed here but isn't worth destroying either. |
| **LoRA** | Viable | Low-rank adapters on attention + MLP projection layers, base weights frozen. Captures a narrow classification task fully at a fraction of full-FT's memory/compute. |
| **QLoRA** | **Chosen** | Same idea as LoRA, but the frozen base model is loaded in 4-bit quantized precision, cutting GPU memory further. This is the deciding factor: it lets the same training job run on smaller/cheaper hardware without a measurable accuracy cost for a task this narrow, which matters when the exact GPU budget isn't fixed in advance. |

**What would change this decision**: if the eval loop (§4) revealed the
task actually needs broader reasoning (e.g. inferring sentiment from
sarcasm or indirect phrasing that a small QLoRA-tuned model consistently
misses), the next step would be trying a larger base model with QLoRA
before ever reaching for full fine-tuning — the technique choice and the
model-size choice are separate levers, and both are cheaper to turn than
full FT.

---

## 4. Training pipeline

### 4.1 Tooling

- **First pass**: Hugging Face `transformers` + `peft` (for the LoRA/QLoRA
  adapter machinery) + `TRL`'s `SFTTrainer`. This stack is extensively
  documented, has a large community, and is easy for a reviewer or teammate
  to reason about without learning a new framework.
- **If iterating across many similar fine-tunes** (e.g. per-region models,
  or repeated retrains as the taxonomy evolves): Axolotl or LLaMA-Factory,
  since their config-driven (YAML) workflow removes per-experiment
  boilerplate — genuinely useful once this becomes a repeated process
  rather than a one-off.

### 4.2 Job structure

```
Frozen base weights (4-bit quantized, QLoRA)
        │
        ▼
QLoRA adapter on attention + MLP projection layers
        │
        ▼
Classification-style prompt template, 8 categories enumerated explicitly
        │
        ▼
1-2 epochs over the curated training set
        │
        ▼
Early stopping on held-out validation split (not the frozen test set)
        │
        ▼
Adapter checkpoint saved per epoch / eval interval
```

- **Epochs**: 1–2 is a reasonable starting point for a dataset this size
  (§2.3) — more risks overfitting a few thousand examples; this is a
  starting value to tune against the validation curve, not a fixed rule.
- **Prompt template**: a fixed instruction template listing all 8
  categories explicitly in the prompt every time, so the model is never
  guessing at the label space.
- **Reproducibility**: fixed random seed, pinned library versions, and the
  exact training config (base model revision, LoRA rank/alpha, learning
  rate, batch size) checked into version control alongside the dataset
  version used — so any run can be reproduced or audited later.
- **Experiment tracking**: log every run (config + metrics) to a tracker
  (e.g. Weights & Biases or MLflow) so the eventual production model choice
  in §4/§5 is backed by a comparable history of runs, not just the last one
  that happened to finish.

---

## 5. Evaluation

### 5.1 Metrics tracked

| Metric | Why it's tracked |
|---|---|
| **Macro F1** (primary) | Weights every one of the 8 classes equally — the metric that actually reflects whether rare categories are being learned, not just the common ones (see §2.5) |
| Per-class precision/recall/F1 | A single macro number can hide one category collapsing to 0 recall while others compensate on average; per-class breakdown is what actually drives round-2 data collection (§2.4) |
| Confusion matrix | Shows *which* categories get confused for which — e.g. if *Negative – Staff* and *Negative – Wait Time* are frequently swapped, that's a labeling-ambiguity signal (§2.2), not necessarily a model failure |
| Overall accuracy (secondary) | Reported for context/comparability, never used alone to make a go/no-go call, since it can be misleadingly high under class imbalance |
| Agreement rate vs. GPT-4o | Direct head-to-head comparison on the same frozen held-out set the fine-tuned model never saw — the metric that answers "is this actually as good as what we're replacing?" |
| Latency / cost per 1,000 classifications | The other half of the business case — a fine-tuned model that's only marginally cheaper than GPT-4o at similar quality doesn't justify the engineering investment |

### 5.2 The production-readiness gate

The fine-tuned model does **not** replace GPT-4o just because its accuracy
is "good" in isolation. Concrete bar:

1. **Per-category agreement-with-human-label rate** must match GPT-4o's own
   agreement-with-human-label rate **within a small margin, on every
   category individually** — not just in aggregate. A model that's
   excellent on 7 categories and terrible on the 8th does not pass, even
   if the average looks fine.
2. **Shadow-mode period**: before any traffic actually depends on the new
   model's classification, run it *alongside* GPT-4o on the same live
   traffic for a defined period (e.g. 1–2 weeks of real volume), logging
   both outputs without acting on the fine-tuned model's output yet. This
   catches distribution drift or edge cases that a static held-out test set
   can't — real production text is messier than any curated eval set.
3. Only after shadow-mode results independently confirm the held-out-set
   numbers does the fine-tuned model take over the live classification
   route.

If a category never clears the bar, a hybrid approach — route that
specific category's classifications to the frontier model as a fallback
while the fine-tuned model handles the rest — is a legitimate interim
state, not a failure of the whole project.

---

## 6. Serving

### 6.1 Architecture

```
                     Existing API / routing layer
                              │
              ┌───────────────┴───────────────┐
              ▼                                ▼
     Existing LLM routes                Classification route
    (unrelated features,                 (survey free-text
     unaffected)                          sentiment+topic)
                                                │
                                                ▼
                                   Base model process (vLLM / TGI)
                                       + fine-tuned LoRA adapter
                                     loaded alongside other adapters
```

- **Adapter-swapping**, not a separate deployment: vLLM and TGI both
  support serving multiple LoRA adapters on top of one loaded base model
  process. The survey-classification route selects this specific adapter
  at request time; every other route on the same server continues using
  the base model or a different adapter, completely unaffected.
- **No new GPU footprint** is needed purely to add this classifier — it
  rides on infrastructure that may already exist for other LLM routes,
  since the marginal cost of one more small adapter is minimal compared to
  spinning up a dedicated model server.
- **Rollback**: because the adapter is a separate artifact from the base
  model, a bad fine-tune is rolled back by simply pointing the route back
  at the previous adapter version (or the GPT-4o fallback) — no base model
  redeploy required.

### 6.2 Fallback behavior

Keep GPT-4o as an explicit fallback path for:
- Categories that haven't cleared the production-readiness gate (§5.2).
- Low-confidence classifications from the fine-tuned model (below a
  calibrated confidence threshold) — route those specific cases to the
  frontier model rather than accepting a low-confidence guess, trading a
  small amount of the cost savings for reliability on the hardest cases.
- Any input that looks anomalous relative to the training distribution
  (very long text, unexpected language, etc.) — a cheap heuristic gate
  before the classifier, not a model decision itself.

---

## 7. Future-proofing

The core risk to avoid: coupling the pipeline tightly to *this specific*
label taxonomy, *this specific* base model, or *this specific* serving
framework, such that any future change becomes a code rewrite instead of a
config change.

### 7.1 Canonical internal schema

Every training example — regardless of its original source (frontier-model
bootstrap, human-labeled, active-learning round-2, a future data source
entirely) — is normalized into one canonical shape before it ever reaches
the training pipeline:

```json
{
  "text": "The food was great but the wait time was too long.",
  "label": "negative_wait_time",
  "metadata": {
    "source": "survey",
    "business_id": "b01",
    "date": "2026-05-14",
    "label_source": "human_review"
  }
}
```

Any new data source maps into this schema via a thin adapter layer, rather
than the training code itself learning a new input format each time.

### 7.2 Versioned, config-driven taxonomy

The 8-category label set and the prompt template live in a **versioned
config file**, not hardcoded into training or serving code. Adding a 9th
category, splitting one category into two, or renaming a category becomes
a config diff plus a retrain — never a code change. This also makes it
possible to run two taxonomy versions side-by-side during a transition.

### 7.3 Decoupled pipeline stages

```
Source data  →  Canonical schema  →  Training pipeline  →  Model artifact  →  Evaluation contract  →  Serving adapter
```

Each arrow is a well-defined interface, not an implicit assumption baked
into the next stage's code:
- Swapping the **training backend** (HF Trainer → Axolotl, say) only
  touches the "training pipeline" stage — it still consumes the same
  canonical schema and produces an artifact conforming to the same
  evaluation contract.
- Swapping the **base model** (Llama 3.1 8B → a future, better small model)
  only touches the "training pipeline" and "model artifact" stages — the
  data and evaluation contract are unaffected.
- Swapping the **serving framework** (vLLM → something else) only touches
  the last stage, provided the model artifact still exports in a format
  that framework accepts (a standard LoRA adapter format, not something
  bespoke to one serving stack).

### 7.4 Drift monitoring, not a fixed retrain calendar

Log every production prediction (input + output + confidence) so the input
distribution can be compared against the training distribution over time.
Re-run the active-sampling labeling loop (§2.4) **when drift crosses a
defined threshold**, not on an arbitrary fixed schedule — this avoids both
wasted retraining effort when nothing has changed and stale models when
something has (e.g. a new menu item shifts the vocabulary of food-quality
complaints).

---

## Summary

| Question from the brief | One-line answer |
|---|---|
| Data strategy / labeled examples | Frontier-bootstrap + human QA on a stratified/active-learning subset; ~3,000–5,000 examples to start |
| Model & technique | Llama 3.1 8B (or similar), QLoRA — task and label space are narrow, quantized base cuts GPU cost with no meaningful accuracy trade-off here |
| Training pipeline | HF `transformers`+`peft`+`TRL` first pass; Axolotl/LLaMA-Factory if scaling to many fine-tunes |
| Evaluation | Macro F1 + per-class breakdown + confusion matrix + GPT-4o agreement rate; production gate requires matching GPT-4o per-category, confirmed in shadow mode before cutover |
| Serving | Adapter-swapping on the existing base model process (vLLM/TGI multi-LoRA); GPT-4o kept as a fallback for low-confidence/unready categories |
| Future-proofing | Canonical schema for all training data, versioned taxonomy/prompt config, decoupled pipeline stages, drift-triggered (not calendar-triggered) retraining |
