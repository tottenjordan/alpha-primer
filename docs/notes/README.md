# Project Notes Index

Top-level index of session notes and key repository files (kept under 200 lines).

## Key Repository Files

- [CODE_STANDARDS.md](../../CODE_STANDARDS.md) — Engineering guidelines, tooling standards (uv, ruff, ty, pytest), and collaboration rules.
- [GEMINI.md](../../GEMINI.md) — Agent context and instructions referencing CODE_STANDARDS.md.
- [USE_CASE.md](../../USE_CASE.md) — Specification for the Multi-Echelon & Perishable Inventory Replenishment Digital Twin candidate use case.
- [USER_GUIDE.md](../USER_GUIDE.md) — End-to-end operational user manual for the repository and execution modes.
- [DATASET.md](../../examples/inventory_replenishment/DATASET.md) — Technical dataset specification for the inventory replenishment digital twin benchmark.
- `.env` — Local environment configuration.

## Topic Notes

- [alphaevolve_architecture.md](alphaevolve_architecture.md) — Module resolution for standalone scripts, signal-free worker timeouts, causal time indexing, and mock client iteration.
- [alphaevolve_api_wire_spec.md](alphaevolve_api_wire_spec.md) — Discovery Engine v1alpha AlphaEvolve REST endpoints, wire schemas, lock tokens, and start/submission payloads.
- [ci_tooling.md](ci_tooling.md) — uv lockfile generation, internal Airlock proxies vs public PyPI index for GitHub Actions runners.
- [cloud_resources_and_execution.md](cloud_resources_and_execution.md) — Cloud resources created during execution, serverless Discovery Engine architecture, UI/observability, and local simulation runtime.
- [interactive_dashboard.md](interactive_dashboard.md) — Interactive executive dashboard architecture, dual-mode web serving, Safe DOM, Retina Canvas 2D, and What-If sandbox.
- [abstract_evaluator_protocol.md](abstract_evaluator_protocol.md) — Multi-tier evaluation protocol (syntax, smoke, validation, holdout), early-exit performance, and custom domain evaluator authoring guide.
- [candidate_sandboxing.md](candidate_sandboxing.md) — Multi-mode process/subprocess sandboxing, POSIX memory limits (RLIMIT_AS), unblockable timeouts (SIGKILL), and crash/signal trapping.
- [google_cloud_run_hosting.md](google_cloud_run_hosting.md) — Cloud Run containerization, deployment automation, and Gemini Enterprise (Discovery Engine v1alpha) external agent registration.
- [../architecture/README.md](../architecture/README.md) — Reference architectures and workflow diagrams (end-to-end evolutionary topology, Cloud Run integration, digital twin loop).




