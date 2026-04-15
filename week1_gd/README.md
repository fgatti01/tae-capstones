# TAE Week 1 Capstone — Gradient-Based Optimization (GD/SGD)

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fgatti01/tae-capstones/blob/main/week1_gd/notebooks/capstone.ipynb)

Implements gradient descent and stochastic gradient descent on the piecewise objective

$$f(x) = \left|\tfrac{1}{2}x^3 - \tfrac{3}{2}x^2\right| + \tfrac{1}{2}x$$

from the Week 1 Gradient-Based Optimization case study (TAE Program — Core Track).
Global minimizer: $x^\star = 1 - \tfrac{2}{3}\sqrt{3} \approx -0.1547$, with $f(x^\star) = \tfrac{3}{2} - \tfrac{8}{9}\sqrt{3}$.

## What the notebook does

1. Defines `f` and the piecewise `f_prime` (with subgradient at the kink `x=3`).
2. Analytic-vs-numeric (central difference) gradient check.
3. GD with constant step `η=0.15` from three initial points `x0 ∈ {-1.0, 0.5, 2.0}`.
4. GD step-size sensitivity sweep `η ∈ {0.05, 0.10, 0.15, 0.20}` at `x0=0.5`.
5. Overshooting example `η=0.6` showing oscillation.
6. SGD (K=200) with constant vs diminishing schedule `η_k = η_0/(1+γk)`.
7. Interpretation markdown for each experiment.

All figures are saved to `assets/` with `dpi=150`.

## Run

Colab: click the badge above.

Local:

```
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
jupyter nbconvert --to notebook --execute notebooks/capstone.ipynb --output capstone.executed.ipynb
```

## Deliverables (rubric)

- [x] Reproducibility — fixed seed, runs top-to-bottom on fresh runtime
- [x] Numerical check — analytic vs central-difference gradient
- [x] Visualization — 6 labeled plots, axes/legends/titles
- [x] Interpretation — markdown after each experiment
- [x] Packaging — README + requirements.txt + Colab badge
