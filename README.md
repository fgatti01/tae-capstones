<img src="https://theaiengineer.dev/tae_logo_gw_flatter.png" width="30%" align="right" alt="The AI Engineer">

# TAE Capstones

Capstone deliverables for **[The AI Engineer (TAE)](https://theaiengineer.dev/tae/tae.html)** course by **Dr. Yves J. Hilpisch** ([The Python Quants GmbH](https://tpq.io)).

Four weekly capstones, each self-contained with its own README, notebook (or package), requirements, and assets.

| Week | Topic | Folder |
|---|---|---|
| 1 | Gradient-Based Optimization (GD/SGD) | [week1_gd/](week1_gd/) |
| 2 | Backpropagation — NumPy → autograd → `nn.Module` | [week2_backprop/](week2_backprop/) |
| 3 | Tiny decoder-only Transformer | [week3_transformer/](week3_transformer/) |
| 4 | MCP Incident Command Agent | [week4_mcp_agent/](week4_mcp_agent/) |

## Run in Colab

- Week 1: [Open in Colab](https://colab.research.google.com/github/fgatti01/tae-capstones/blob/main/week1_gd/notebooks/capstone.ipynb)
- Week 2: [Open in Colab](https://colab.research.google.com/github/fgatti01/tae-capstones/blob/main/week2_backprop/notebooks/capstone.ipynb)
- Week 3: [Open in Colab](https://colab.research.google.com/github/fgatti01/tae-capstones/blob/main/week3_transformer/notebooks/capstone.ipynb)

## Run locally

Each week is independent. From the repo root:

```bash
cd week1_gd   # or week2_backprop / week3_transformer
python -m venv .venv
# Windows:   .venv\Scripts\activate
# Unix:      source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebooks/capstone.ipynb
```

Week 4 is a Python package with tests and a CLI:

```bash
cd week4_mcp_agent
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pytest -q
python -m incident_agent.cli run-demo
```

See each week's README for details, rubric alignment, and expected outputs.

---

Submitted by **Fernando Gatti** — [fgatti01](https://github.com/fgatti01).
