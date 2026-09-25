# AlphaEvolve Enterprise Use Cases Gallery

This directory contains standalone, end-to-end AlphaEvolve code samples demonstrating how to architect and implement evolutionary optimization on Google Cloud with Gemini Enterprise.

---

## Catalog of Use Cases

| Directory | Vertical | Domain | Method / Approach | Evaluation Paradigm | Primary Metric |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [`inventory_replenishment/`](inventory_replenishment/README.md) | Retail & Grocery | Supply Chain & Warehousing | Dynamic $(s, S)$ with FIFO Perishable Expiration | **Simulation** (Digital Twin) | Total Cost Reduction % |

---

## Architecture of an Example

Every example directory follows a standardized contract:

```
examples/<use_case>/
├── README.md               # Overview, business problem, mathematical objective, and instructions
├── instructions.md         # Domain prompt context, formulation, and search space constraints
├── run_evolution.py        # Executable entrypoint (supports --dry-run for local offline testing)
├── src/
│   ├── program.py          # Seed baseline algorithm bounded by # EVOLVE-BLOCK-START / END
│   ├── simulator.py        # Domain environment or dataset simulator (with causal isolation)
│   ├── evaluate.py         # 3-tier evaluator returning numerical Scores and text Insights
│   └── report.py           # Holdout test set validation and visual report generation
└── tests/                  # Fast, offline pytest suite verifying simulator and evaluator correctness
```

---

## Adding a Custom Use Case

To build your own AlphaEvolve use case:
1. Duplicate a template folder (e.g. `cp -r examples/inventory_replenishment examples/my_use_case`).
2. Write your seed algorithm in `src/program.py` bounded by `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END`.
3. Build your domain evaluation harness in `src/evaluate.py` returning `EvaluationResult`.
4. Define your problem formulation, state variables, and constraints in `instructions.md`.
5. Test locally using dry-run mode: `uv run python examples/my_use_case/run_evolution.py --dry-run`.
