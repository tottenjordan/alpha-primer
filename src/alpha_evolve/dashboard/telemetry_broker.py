"""Real-time telemetry event broker for broadcasting optimization runs and candidates.

Maintains thread-safe in-memory queues for Server-Sent Events (SSE) subscribers
and persists a bounded history buffer so late-joining dashboard clients receive
current run context immediately upon connection.
"""

from __future__ import annotations

import collections
import datetime
import logging
import queue
import threading
from typing import Any, Literal, TypedDict

logger = logging.getLogger(__name__)

EventType = Literal[
    "run_started",
    "candidate_evaluated",
    "milestone_discovered",
    "run_completed",
    "heartbeat",
]


class TelemetryEvent(TypedDict):
    """Schema for structured telemetry events emitted during evolution."""

    event_type: EventType
    timestamp_utc: str
    data: dict[str, Any]


class LiveTelemetryBroker:
    """Thread-safe event broker managing dashboard SSE subscribers and run state."""

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "status": "IDLE",
            "experiment_name": None,
            "max_programs": 0,
            "primary_metric": "cost_reduction_pct",
            "evaluated_count": 0,
            "best_score": -float("inf"),
            "best_candidate_id": None,
            "latest_candidate": None,
            "started_at": None,
            "completed_at": None,
        }

    def __init__(self, buffer_size: int = 500) -> None:
        self.buffer_size = buffer_size
        self._lock = threading.RLock()
        self._subscribers: set[queue.Queue[TelemetryEvent]] = set()
        self._history: collections.deque[TelemetryEvent] = collections.deque(maxlen=buffer_size)
        self._current_state: dict[str, Any] = self._default_state()

    def subscribe(self) -> queue.Queue[TelemetryEvent]:
        """Subscribe to the event stream, receiving a dedicated thread-safe queue."""
        q: queue.Queue[TelemetryEvent] = queue.Queue(maxsize=1000)
        with self._lock:
            self._subscribers.add(q)
            # Replay recent history if available
            for event in list(self._history):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    break
        return q

    def unsubscribe(self, q: queue.Queue[TelemetryEvent]) -> None:
        """Remove a subscriber queue when client disconnects."""
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: TelemetryEvent) -> None:
        """Publish a new event to all active subscribers and update state snapshot."""
        with self._lock:
            self._history.append(event)
            self._update_state_from_event(event)

            stale_queues: list[queue.Queue[TelemetryEvent]] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    # Subscriber dropped behind; mark for removal
                    stale_queues.append(q)

            for stale in stale_queues:
                self._subscribers.discard(stale)

    def _update_state_from_event(self, event: TelemetryEvent) -> None:
        """Update internal state snapshot based on event payload."""
        etype = event.get("event_type")
        data = event.get("data", {})
        now_str = event.get("timestamp_utc") or datetime.datetime.now(datetime.UTC).isoformat()

        if etype == "run_started":
            self._current_state["status"] = "RUNNING"
            self._current_state["experiment_name"] = data.get("experiment_name")
            self._current_state["max_programs"] = data.get("max_programs", 0)
            self._current_state["primary_metric"] = data.get("primary_metric", "cost_reduction_pct")
            self._current_state["evaluated_count"] = 0
            self._current_state["best_score"] = -float("inf")
            self._current_state["best_candidate_id"] = None
            self._current_state["latest_candidate"] = None
            self._current_state["started_at"] = now_str
            self._current_state["completed_at"] = None

        elif etype == "candidate_evaluated":
            self._current_state["evaluated_count"] += 1
            self._current_state["latest_candidate"] = data
            score = data.get("score")
            if score is not None and score > self._current_state["best_score"]:
                self._current_state["best_score"] = float(score)
                self._current_state["best_candidate_id"] = data.get("program_id")

        elif etype == "run_completed":
            self._current_state["status"] = "COMPLETED"
            self._current_state["completed_at"] = now_str
            if "best_score" in data:
                self._current_state["best_score"] = float(data["best_score"])
            if "evaluated_count" in data:
                self._current_state["evaluated_count"] = int(data["evaluated_count"])

    def get_history(self) -> list[TelemetryEvent]:
        """Return a copy of the recent event history."""
        with self._lock:
            return list(self._history)

    def get_current_state(self) -> dict[str, Any]:
        """Return a snapshot of current run status and metrics."""
        with self._lock:
            return dict(self._current_state)

    def clear(self) -> None:
        """Reset history and subscribers (e.g. for testing)."""
        with self._lock:
            self._history.clear()
            self._subscribers.clear()
            self._current_state = self._default_state()


_GLOBAL_BROKER: LiveTelemetryBroker | None = None
_GLOBAL_LOCK = threading.Lock()


def get_global_broker() -> LiveTelemetryBroker:
    """Obtain or initialize the application-wide singleton LiveTelemetryBroker."""
    global _GLOBAL_BROKER
    if _GLOBAL_BROKER is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_BROKER is None:
                _GLOBAL_BROKER = LiveTelemetryBroker()
    return _GLOBAL_BROKER
