"""Dashboard generation and trajectory compilation for AlphaEvolve."""

from __future__ import annotations

from .telemetry_broker import LiveTelemetryBroker, TelemetryEvent, get_global_broker

__all__ = ["LiveTelemetryBroker", "TelemetryEvent", "get_global_broker"]
