"""In-memory store for the Incident Command Agent.

Represents both the episodic log (one entry per Observe→Plan→Act→Learn cycle)
and the semantic slice served back via the MCP resource surface
(memory://alerts/latest). See §5.4 of the handout.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class MemoryDelta:
    alert_id: str
    correlation_id: str
    phase: str                     # one of: observe, plan, act, learn
    action: str                    # tool name or "observe"/"learn"
    payload: dict[str, Any]        # tool args / observation
    result_summary: str            # short human-readable summary
    latency_ms: float
    timestamp: str                 # ISO 8601 UTC

    @classmethod
    def new(cls, alert_id: str, correlation_id: str, phase: str, action: str,
            payload: dict, result_summary: str, latency_ms: float) -> "MemoryDelta":
        return cls(
            alert_id=alert_id,
            correlation_id=correlation_id,
            phase=phase,
            action=action,
            payload=payload,
            result_summary=result_summary,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )


@dataclass
class MemoryStore:
    alerts: list[dict] = field(default_factory=list)
    deltas: list[MemoryDelta] = field(default_factory=list)

    def append(self, delta: MemoryDelta) -> None:
        self.deltas.append(delta)

    def latest_snapshot(self, alert_id: str | None = None, n_deltas: int = 6) -> dict:
        """Served by the MCP resource memory://alerts/latest."""
        alert = self.alerts[-1] if self.alerts else None
        if alert_id is not None:
            alert = next((a for a in self.alerts if a["id"] == alert_id), alert)
        relevant = [asdict(d) for d in self.deltas if alert is None or d.alert_id == alert["id"]]
        return {
            "alert": alert,
            "recent_deltas": relevant[-n_deltas:],
            "delta_count": len(relevant),
        }

    def export(self) -> dict:
        return {"alerts": list(self.alerts), "deltas": [asdict(d) for d in self.deltas]}


# Stable correlation IDs for deterministic replay in tests.
def id_generator(prefix: str = "loop") -> "itertools.count":
    return itertools.count(1)


def mint_correlation_id(counter: "itertools.count", run_id: str) -> str:
    return f"{run_id}-{next(counter):03d}"
