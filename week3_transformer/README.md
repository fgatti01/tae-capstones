# TAE Week 3 Capstone — Tiny Decoder-Only Transformer

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fgatti01/tae-capstones/blob/main/week3_transformer/notebooks/capstone.ipynb)

Implements the Week 3 handout end-to-end: scaled dot-product attention → multi-head
self-attention → positional encodings → pre-LN transformer block → tiny decoder-only LM →
training, sampling, and attention visualization.

## Components (all from scratch)

- `scaled_dot_product_attention` — validated against the handout's §4.3 numeric example
  (T=3, d_k=d_v=2) and against a naïve double-loop reference.
- `MultiHeadAttention` — single QKV projection, causal mask, `B×H×T×d_head` layout.
- `PositionalEncoding` — sinusoidal, registered as buffer.
- `TransformerBlock` — Pre-LN (LN → MHA → residual, LN → FFN → residual).
- `TinyTransformerLM` — embedding + PE + L blocks + vocab projection.

## Task

Character-level language modeling on a small embedded English corpus (~6 kB of text).
90/10 train/val split, block size 64, vocab ≈ 40 chars. Config:
`d_model=96, n_heads=4, n_layers=3, d_ff=256, block=64, batch=32`, Adam lr=3e-4.

## Sanity checks baked in

- Attention formula matches hand calculation on §4.3 tiny example.
- Causal mask zeros strictly-upper-triangular attention weights.
- Uninitialized-model loss ≈ `log(V)` (uniform-logit baseline).
- `loss.backward()` produces a finite gradient for every parameter.
- Overfit test on a trivial repeating pattern reaches ≈0 loss.
- Checkpoint save/load produces identical logits.

## Run

Colab: click the badge above.

Local:

```
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
jupyter nbconvert --to notebook --execute notebooks/capstone.ipynb --output capstone.executed.ipynb
```

## Rubric coverage

- [x] **Correctness** — attention + block + forward + causal mask all verified
- [x] **Engineering hygiene** — single `Config`, seed, checkpoint, structured log
- [x] **Reporting** — sampling gallery (greedy + temperature 0.8 / 1.2), attention heatmap, README
