# AlphaEvolve Discovery Engine REST API Wire Specifications

This note captures non-obvious REST API wire requirements and schemas discovered when integrating directly with Gemini Enterprise AlphaEvolve endpoints.

---

## 1. Resource Hierarchy & Endpoints

- **Discovery Engine Base URL**: `https://discoveryengine.googleapis.com/v1alpha`
- **Session Provisioning**:
  - `POST {base_url}/projects/{project}/locations/{loc}/collections/{coll}/engines/{engine}/sessions`
  - Body: `{"displayName": "AlphaEvolve Session"}`
  - Response: returns `"name": ".../sessions/{session_id}"`.
- **Experiment Creation**:
  - `POST {base_url}/{session_name}/alphaEvolveExperiments`
  - Do **NOT** pass `alphaEvolveExperimentId` as a query parameter (causes `400 Bad Request`).
  - Body structure:
    ```json
    {
      "config": {
        "title": "Experiment Title",
        "problemDescription": "Markdown system prompt and domain guidance",
        "runSettings": {
          "maxPrograms": 5,
          "concurrency": 4
        }
      }
    }
    ```
- **Initial Seed Program Registration**:
  - `POST {base_url}/{experiment_name}/alphaEvolvePrograms`
  - Content must contain `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END` tags around editable Python code.
  - Body structure:
    ```json
    {
      "content": {
        "files": [{"path": "initial_program.py", "content": "<seed_code>"}]
      },
      "evaluation": {
        "scores": {"scores": [{"metric": "score", "score": <baseline_score>}]}
      }
    }
    ```
- **Starting Experiment (`:start`)**:
  - `POST {base_url}/{experiment_name}:start`
  - Requires the `initialProgram` resource path string:
    ```json
    {
      "name": "<experiment_name>",
      "initialProgram": "<seed_program_resource_name>"
    }
    ```
- **Acquiring Candidates (`:acquirePrograms`)**:
  - `POST {base_url}/{experiment_name}:acquirePrograms`
  - Body: `{"parent": "<experiment_name>", "desiredProgramsCount": <count>}`
  - Response: contains `"programs"` or `"alphaEvolvePrograms"`, and a `"lockToken"`.
- **Submitting Evaluations (`:submitProgramsEvaluations`)**:
  - `POST {base_url}/{experiment_name}:submitProgramsEvaluations`
  - Body:
    ```json
    {
      "parent": "<experiment_name>",
      "evaluationSubmissions": [
        {
          "program": "<program_resource_name>",
          "lockToken": "<lock_token>",
          "evaluation": {
            "scores": {"scores": [{"metric": "score", "score": <float>}]},
            "insights": {"insights": [{"label": "...", "text": "..."}]}
          }
        }
      ]
    }
    ```

---

## 2. Timing & Polling Guidance
- The Gemini Enterprise LLM mixture requires ~30–60 seconds after `:start` to synthesize initial candidate mutations.
- Set controller `idle_timeout_s` to at least 300 seconds and poll `:acquirePrograms` every 5 seconds.
