"""Discovery Engine AlphaEvolve REST API Client and Offline Mock Client."""

from __future__ import annotations

import logging
import random
import re
import threading
import warnings
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

from .models import (
    AlphaEvolveEvaluationSubmission,
    ExperimentConfig,
    ProgramCandidate,
)

logger = logging.getLogger(__name__)


class AlphaEvolveClient:
    """Production REST client for Google Cloud Gemini Enterprise / Discovery Engine AlphaEvolve API."""

    def __init__(
        self,
        project_id: str,
        location: str = "global",
        collection: str = "default_collection",
        engine_id: str = "alpha-evolve-experiment-engine",
        assistant_id: str = "default_assistant",
        base_url: str = "discoveryengine.googleapis.com",
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.collection = collection
        self.engine_id = engine_id
        self.assistant_id = assistant_id

        prefix = ""
        if location.upper() in {"EU", "US"}:
            prefix = f"{location.lower()}-"
        self.base_url = f"https://{prefix}{base_url}/v1alpha"

        self.engine_path = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"collections/{self.collection}/engines/{self.engine_id}"
        )

        self._credentials: Any = None
        self._auth_request: Any = None
        self._auth_lock = threading.Lock()
        self._http_client = httpx.Client(timeout=30.0)

    def _get_access_token(self) -> str:
        """Retrieve valid OAuth2 access token via Application Default Credentials (ADC)."""
        with self._auth_lock:
            if self._credentials is None:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="Your application has authenticated using end user credentials",
                    )
                    self._credentials, _ = google.auth.default(
                        scopes=["https://www.googleapis.com/auth/cloud-platform"]
                    )
                self._auth_request = google.auth.transport.requests.Request()
            if not self._credentials.valid:
                self._credentials.refresh(self._auth_request)
            return str(self._credentials.token)

    def _headers(self) -> dict[str, str]:
        """Headers required for Discovery Engine requests."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._get_access_token()}",
            "x-goog-user-project": self.project_id,
        }

    def create_session(self) -> str:
        """Create a new conversational session under the engine."""
        url = f"{self.base_url}/{self.engine_path}/sessions"
        payload = {"displayName": "AlphaEvolve Session"}
        resp = self._http_client.post(url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()
        session_name: str | None = data.get("name")
        if not session_name:
            raise RuntimeError(f"Could not extract session name from response: {data}")
        return session_name

    def create_experiment(self, session_name: str, config: ExperimentConfig) -> str:
        """Register a new AlphaEvolveExperiment under the session."""
        url = f"{self.base_url}/{session_name}/alphaEvolveExperiments"

        req_config = {
            "title": config.experiment_name,
            "problemDescription": config.user_instructions,
            "runSettings": {
                "maxPrograms": config.run_settings.max_programs,
                "concurrency": config.run_settings.parallel_workers,
            },
        }

        resp = self._http_client.post(
            url,
            headers=self._headers(),
            json={"config": req_config},
        )
        resp.raise_for_status()
        exp_data = resp.json()
        experiment_name: str | None = exp_data.get("name")
        if not experiment_name:
            raise RuntimeError(f"Could not extract experiment name from response: {exp_data}")
        return experiment_name

    def create_initial_program(
        self, experiment_name: str, seed_code: str, baseline_score: float = 0.0
    ) -> str:
        """Submit the initial seed program to seed the evolutionary population."""
        url = f"{self.base_url}/{experiment_name}/alphaEvolvePrograms"
        payload = {
            "content": {
                "files": [{"path": "initial_program.py", "content": seed_code}],
            },
            "evaluation": {"scores": {"scores": [{"metric": "score", "score": baseline_score}]}},
        }
        resp = self._http_client.post(url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        prog_data = resp.json()
        prog_name: str = prog_data.get("name", "seed_program")
        return prog_name

    def start_experiment(self, experiment_name: str, initial_program_name: str) -> None:
        """Trigger start of the evolutionary generation cycle."""
        url = f"{self.base_url}/{experiment_name}:start"
        payload = {
            "name": experiment_name,
            "initialProgram": initial_program_name,
        }
        resp = self._http_client.post(url, headers=self._headers(), json=payload)
        resp.raise_for_status()

    def acquire_programs(self, experiment_name: str, count: int = 2) -> list[ProgramCandidate]:
        """Poll the API to acquire newly generated program candidates awaiting evaluation."""
        url = f"{self.base_url}/{experiment_name}:acquirePrograms"
        payload = {"parent": experiment_name, "desiredProgramsCount": count}
        resp = self._http_client.post(url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

        candidates: list[ProgramCandidate] = []
        raw_programs = data.get("programs") or data.get("alphaEvolvePrograms", [])
        default_lock = data.get("lockToken", "")
        for item in raw_programs:
            prog_name = item.get("name", f"prog_{int(random.random() * 1e6)}")
            files = item.get("content", {}).get("files", [])
            code = files[0].get("content", "") if files else ""
            lock_token = item.get("lockToken") or default_lock
            candidates.append(
                ProgramCandidate(
                    program_id=prog_name,
                    code=code,
                    lock_token=lock_token,
                )
            )

        return candidates

    def submit_evaluations(
        self, experiment_name: str, submissions: list[AlphaEvolveEvaluationSubmission]
    ) -> None:
        """Submit completed evaluation scores and diagnostic insights back to AlphaEvolve."""
        url = f"{self.base_url}/{experiment_name}:submitProgramsEvaluations"
        for sub in submissions:
            sub_dict = sub.model_dump(exclude_none=True)
            payload = {
                "parent": experiment_name,
                "evaluationSubmissions": [sub_dict],
            }
            resp = self._http_client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()


class MockAlphaEvolveClient:
    """Offline mock client simulating Gemini AlphaEvolve evolutionary synthesis locally.

    Enables testing and dry-run execution without cloud permissions or network latency.
    """

    def __init__(self, seed_code: str) -> None:
        self.seed_code = seed_code
        self.iteration = 0
        self.evaluated_count = 0
        self.experiment_name = "mock_experiment_session"
        self._history: list[ProgramCandidate] = []

    def create_session(self) -> str:
        return "sessions/mock-session-001"

    def create_experiment(self, session_name: str, config: ExperimentConfig) -> str:
        return f"{session_name}/alphaEvolveExperiments/mock-exp-001"

    def create_initial_program(
        self, experiment_name: str, seed_code: str, baseline_score: float = 0.0
    ) -> str:
        self.seed_code = seed_code
        return f"{experiment_name}/alphaEvolvePrograms/seed"

    def start_experiment(self, experiment_name: str, initial_program_name: str = "") -> None:
        pass

    def acquire_programs(self, experiment_name: str, count: int = 1) -> list[ProgramCandidate]:
        """Synthesize candidate programs by mutating parameters and logic in the evolve block."""
        candidates: list[ProgramCandidate] = []
        for _ in range(count):
            self.iteration += 1
            prog_id = f"{experiment_name}/alphaEvolvePrograms/candidate_{self.iteration:03d}"

            mutated_code = self._mutate_seed_code(self.seed_code, self.iteration)
            candidates.append(
                ProgramCandidate(
                    program_id=prog_id,
                    code=mutated_code,
                    iteration=self.iteration,
                )
            )
        return candidates

    def submit_evaluations(
        self, experiment_name: str, submissions: list[AlphaEvolveEvaluationSubmission]
    ) -> None:
        self.evaluated_count += len(submissions)

    def _mutate_seed_code(self, base_code: str, iteration: int) -> str:
        """Apply simple realistic heuristic mutations (varying safety stock multipliers, lookbacks)."""
        code = base_code

        # Mutation 1: Adjust safety stock multiplier z
        new_z = round(1.2 + (iteration % 8) * 0.15, 2)
        code = re.sub(r"z\s*=\s*[0-9\.]+", f"z = {new_z}", code)

        # Mutation 2: Adjust demand lookback window
        lookback = 7 + (iteration % 4) * 7
        code = re.sub(r"lookback_days\s*=\s*\d+", f"lookback_days = {lookback}", code)

        # Mutation 3: Insert promo responsiveness or spoilage discounting
        if iteration >= 2 and "promo_schedule_lookahead" in code:
            promo_boost = "        # Evolved promo awareness\n        promo_multiplier = 1.0 + 0.5 * np.max(promo_schedule[:, :3], axis=1)\n        target_inventory = target_inventory * promo_multiplier\n"
            if "promo_multiplier" not in code and "order_up_to" in code:
                code = code.replace(
                    "orders = np.maximum(0, order_up_to - net_inventory)",
                    f"{promo_boost}        orders = np.maximum(0, target_inventory - net_inventory)",
                )

        return code
