# TAE Week 2 Capstone — Backpropagation from NumPy to nn.Module

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fgatti01/tae-capstones/blob/main/week2_backprop/notebooks/capstone.ipynb)

Implements the Week 2 capstone checklist (Appendix B of the DL Basics handout): a
one-hidden-layer MLP built four ways, with numerical parity verified across all four.

## Stages

1. **Manual NumPy forward + backward** — equations (8)–(10) from the handout; reproduces the
   worked scalar example (`x=[1,-1], y=2 → f=3, L=0.5, δ_f=1`).
2. **Finite-difference gradient check** — central-difference vs analytic on every parameter.
3. **PyTorch tensors without autograd** — numerical parity vs NumPy on the same inputs.
4. **PyTorch autograd** — `loss.backward()` parity vs manual gradients.
5. **`nn.Module` training on XOR** — train/val split, SGD, diagnostics (loss, grad norms,
   fraction of active ReLUs), checkpoint save/load.
6. **`nn.Sequential`** — same computation graph, fewer lines; retrain and compare.

## Task

Binary XOR regression on `x ~ Uniform([-1,1]^2)`, target `y = 1{x1·x2 < 0}`, MSE loss.
200 train / 100 validation samples, fixed seed.

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

- [x] **Reproducibility** — seeded NumPy + Torch RNGs, deterministic runs under 2 min
- [x] **Gradient sanity** — manual-vs-autograd and analytic-vs-numeric both checked (tol 1e-5)
- [x] **Training loop clarity** — explicit `forward → loss → backward → step → zero_grad` block with markdown
- [x] **Validation and metrics** — fixed val split, MSE + accuracy curves saved
- [x] **Engineering hygiene** — config dataclass, structured log, checkpoint round-trip
- [x] **Interpretation** — markdown explaining each parity check and diagnostic
