# AlphaEvolve Cloud Resources & Execution Architecture

This document details what happens during an AlphaEvolve optimization run, what cloud resources are provisioned, where evaluation code executes, and how progress and artifacts are monitored.

---

## 1. Execution Architecture: Hybrid Split-Execution

AlphaEvolve uses a **split execution model**:
- **LLM Reasoning & Mutation Generation**: Executed centrally in Google Cloud's serverless Gemini Enterprise infrastructure.
- **Fitness Evaluation & Simulation**: Executed **locally on your client machine** (or dedicated on-prem/worker nodes).

```mermaid
flowchart TD
    subgraph Local Client / Dev Environment
        Init["run_evolution.py"] --> Client["AlphaEvolveClient"]
        Client --> Loop["Evaluation Controller Loop"]
        WorkerPool["Local Parallel Worker Pool"] --> Simulator["Digital Twin Simulator / Evaluator"]
        Simulator --> LocalArtifacts["Local Artifacts (artifacts/.../)"]
    end

    subgraph Google Cloud (Serverless Gemini Enterprise)
        Engine["Discovery Engine: alpha-evolve-experiment-engine"]
        Session["Session (/sessions/{id})"]
        Experiment["AlphaEvolveExperiment (/alphaEvolveExperiments/{id})"]
        Programs["Generated Program Candidates (/alphaEvolvePrograms/{id})"]
    end

    Client -->|"1. create_session & create_experiment"| Engine
    Engine --> Session --> Experiment
    Client -->|"2. create_initial_program (seed)"| Experiment
    Experiment -->|"3. acquire_programs (LLM mutations)"| Loop
    Loop -->|"4. Execute candidates"| WorkerPool
    WorkerPool -->|"5. submit_evaluations (fitness scores)"| Experiment
    Loop -->|"6. Save top candidate & holdout report"| LocalArtifacts
```

### Why Split Execution?
1. **Zero Data Egress / IP Protection**: Proprietary training data, cost structures, and simulation environments never leave your local environment. The LLM only receives candidate Python code, prompt instructions, and scalar evaluation scores.
2. **Deterministic Evaluation**: Simulation runs directly on local hardware without arbitrary cloud timeout constraints or container overhead.
3. **No Heavy Infrastructure**: No virtual machines, Compute Engine instances, or Kubernetes clusters are provisioned.

---

## 2. Cloud Resources Created During a Run

When running `uv run python examples/.../run_evolution.py`, all created cloud resources are **serverless API resources** within your existing Discovery Engine:

| Resource | REST URI Pattern | Lifecycle & Scope |
| :--- | :--- | :--- |
| **Session** | `projects/{project}/locations/{loc}/collections/{coll}/engines/{engine}/sessions/{session_id}` | Created per experiment run to scope conversational and evolutionary context. |
| **AlphaEvolve Experiment** | `.../sessions/{session_id}/alphaEvolveExperiments/{exp_id}` | Tracks prompt instructions, target optimization metric, and evolutionary generation parameters. |
| **Seed Program** | `.../alphaEvolveExperiments/{exp_id}/alphaEvolvePrograms/seed` | The baseline candidate program that acts as the root of the evolutionary search graph. |
| **Evolved Candidates** | `.../alphaEvolveExperiments/{exp_id}/alphaEvolvePrograms/{program_id}` | Generated mutation candidates created by the Gemini Enterprise LLM mixture awaiting local evaluation. |

> [!NOTE]
> **No persistent compute infrastructure** (e.g., GCE VMs, GKE clusters, Cloud SQL, Persistent Disks) is created or billed. Billing is based on serverless Gemini Enterprise API requests.

---

## 3. User Interface & Observability

### Terminal CLI
- Running the script does **not** launch an automated browser UI.
- Progress is streamed in real-time to the terminal (iteration number, candidate program IDs, safety metrics, cost reductions, and holdout comparisons).

### Google Cloud Console (Optional)
You can inspect the engine, sessions, and assistants in the Google Cloud Console:
- Navigation: **Vertex AI / Gemini Enterprise / Agent Builder** &rarr; **Engines**
- URI: `https://console.cloud.google.com/gen-app-builder/engines`
- Select project: `hybrid-vertex` &rarr; Engine: `alpha-evolve-experiment-engine`.

### Generated Local Artifacts
Upon run completion, all outputs are stored in `artifacts/{use_case}/`:
- `best_evolved_program.py`: Full executable Python source of the top-performing policy.
- `best_evaluation_summary.json`: Benchmark metrics comparing the evolved policy against baseline on train and locked holdout datasets.
