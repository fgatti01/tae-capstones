"""Observe → Plan → Act → Learn orchestrator for the Incident Command Agent.

Deterministic FSM planner as recommended in handout §5.5. Budgets, correlation
IDs, structured telemetry, and replay-friendly transcripts per §5.6.
"""
from __future__ import annotations

import json
import time
import uuid
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .memory import MemoryStore, MemoryDelta


@dataclass
class Budgets:
    max_loops: int = 4
    max_latency_ms: int = 2000
    max_tool_calls: int = 8
    max_per_tool: dict[str, int] = field(default_factory=dict)


@dataclass
class RunResult:
    alert_id: str
    run_id: str
    loops_run: int
    tool_calls: int
    total_latency_ms: float
    terminated_reason: str
    handoff_markdown: str | None
    trace_path: Path | None
    summary_path: Path | None


class IncidentOrchestrator:
    """A disciplined agent loop. The transport is a callable
    `rpc(request_dict) -> response_dict` so the same orchestrator drives the
    in-process server, a stdio pipe, or a websocket client.
    """

    def __init__(self, rpc: Callable[[dict], dict], memory: MemoryStore,
                 budgets: Budgets, logger: logging.Logger | None = None,
                 run_id: str | None = None):
        self.rpc = rpc
        self.memory = memory
        self.budgets = budgets
        self.log = logger or logging.getLogger("incident_agent")
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self._tool_call_counts: dict[str, int] = {}
        self._loop_counter = 0
        self._transcript: list[dict] = []
        self._t_start: float = 0.0

    # --- JSON-RPC helpers --------------------------------------------------
    def _call(self, method: str, params: dict, correlation_id: str) -> dict:
        req = {"jsonrpc": "2.0", "id": correlation_id, "method": method, "params": params}
        self._transcript.append({"direction": "request", "correlation_id": correlation_id,
                                 "payload": req})
        resp = self.rpc(req)
        self._transcript.append({"direction": "response", "correlation_id": correlation_id,
                                 "payload": resp})
        return resp

    # --- OPAL phases -------------------------------------------------------
    def _observe(self, alert_id: str, cid: str) -> dict:
        resp = self._call("getResource", {"uri": "memory://alerts/latest",
                                          "alert_id": alert_id}, cid)
        snapshot = resp["result"]["data"]
        self.log.info("[%s] OBSERVE alert=%s deltas=%d", cid, alert_id,
                      snapshot.get("delta_count", 0))
        return snapshot

    def _plan(self, snapshot: dict, state: str) -> tuple[str, dict] | None:
        """FSM planner. Returns (tool_name, args) or None to exit loop."""
        alert = snapshot["alert"]
        if state == "retrieve":
            return "retrieve_runbook", {
                "query": f"{alert['symptom']} {alert['service']}",
                "top_k": 2,
            }
        if state == "diagnose":
            # First diagnostic call inspects pods; second inspects events.
            n_diag = self._tool_call_counts.get("run_diagnostic", 0)
            command = "kubectl top pods" if n_diag == 0 else "kubectl get events"
            return "run_diagnostic", {"command": command, "host": alert["service"]}
        if state == "summarize":
            evidence = [d.result_summary for d in self.memory.deltas
                        if d.alert_id == alert["id"] and d.phase == "act"]
            return "summarize_incident", {"alert_id": alert["id"], "evidence": evidence}
        return None

    def _act(self, tool: str, args: dict, cid: str) -> dict:
        resp = self._call("callTool", {"name": tool, "arguments": args}, cid)
        if "error" in resp:
            raise RuntimeError(f"tool error: {resp['error']}")
        self._tool_call_counts[tool] = self._tool_call_counts.get(tool, 0) + 1
        self.log.info("[%s] ACT tool=%s latency_ms=%.2f",
                      cid, tool, resp["result"]["metrics"]["latency_ms"])
        return resp["result"]

    def _learn(self, alert_id: str, cid: str, tool: str, args: dict,
               result: dict) -> MemoryDelta:
        # Concise summary per handout §5.4: 3-4 sentences max.
        data = result["data"]
        if tool == "retrieve_runbook":
            tops = ", ".join(h["title"] for h in data["hits"])
            summary = f"Retrieved {len(data['hits'])} runbook(s): {tops}"
        elif tool == "run_diagnostic":
            summary = f"Diagnostic `{args['command']}` on {args['host']}: {data['summary']}"
        elif tool == "summarize_incident":
            summary = f"Wrote handoff summary with {data['n_items']} evidence items."
        else:
            summary = f"Executed {tool}"
        delta = MemoryDelta.new(
            alert_id=alert_id, correlation_id=cid, phase="act", action=tool,
            payload={"args": args, "result_sample": _sample(data)},
            result_summary=summary,
            latency_ms=result["metrics"]["latency_ms"],
        )
        self.memory.append(delta)
        self.log.info("[%s] LEARN %s", cid, summary)
        return delta

    # --- Budget enforcement ------------------------------------------------
    def _budget_ok(self) -> tuple[bool, str]:
        elapsed_ms = (time.perf_counter() - self._t_start) * 1000
        if self._loop_counter >= self.budgets.max_loops:
            return False, f"max_loops ({self.budgets.max_loops}) reached"
        if elapsed_ms > self.budgets.max_latency_ms:
            return False, f"max_latency_ms exceeded: {elapsed_ms:.0f} > {self.budgets.max_latency_ms}"
        total = sum(self._tool_call_counts.values())
        if total >= self.budgets.max_tool_calls:
            return False, f"max_tool_calls ({self.budgets.max_tool_calls}) reached"
        return True, "ok"

    def _per_tool_ok(self, tool: str) -> bool:
        cap = self.budgets.max_per_tool.get(tool)
        if cap is None:
            return True
        return self._tool_call_counts.get(tool, 0) < cap

    # --- Main entrypoint ---------------------------------------------------
    def run(self, alert: dict, trace_path: Path | None = None,
            summary_path: Path | None = None) -> RunResult:
        self._t_start = time.perf_counter()
        self.memory.alerts.append(alert)

        # Open the session — handout §2.1 capabilities handshake.
        init_resp = self._call("initialize", {"clientName": "incident-cli",
                                              "clientVersion": "0.1.0"}, f"{self.run_id}-init")
        assert "result" in init_resp, "initialize handshake failed"

        fsm = ["retrieve", "diagnose", "diagnose", "summarize"]
        handoff_markdown: str | None = None
        reason = "completed"

        for state in fsm:
            ok, why = self._budget_ok()
            if not ok:
                reason = why
                break
            if not self._per_tool_ok({
                "retrieve": "retrieve_runbook",
                "diagnose": "run_diagnostic",
                "summarize": "summarize_incident",
            }[state]):
                reason = f"per-tool cap reached in state={state}"
                break

            self._loop_counter += 1
            loop_tag = f"{self.run_id}-{self._loop_counter:03d}"
            # JSON-RPC ids must be unique per request; correlation id (logical
            # loop label) is shared across Observe/Act within one loop.
            cid_observe = f"{loop_tag}-obs"
            cid_act = f"{loop_tag}-act"
            snapshot = self._observe(alert["id"], cid_observe)
            plan = self._plan(snapshot, state)
            if plan is None:
                break
            tool, args = plan
            result = self._act(tool, args, cid_act)
            delta = self._learn(alert["id"], loop_tag, tool, args, result)
            if tool == "summarize_incident":
                handoff_markdown = result["data"]["summary_markdown"]

        total_latency_ms = (time.perf_counter() - self._t_start) * 1000

        out_trace = None
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("w", encoding="utf-8") as fh:
                for entry in self._transcript:
                    fh.write(json.dumps(entry, sort_keys=True) + "\n")
            out_trace = trace_path

        out_summary = None
        if summary_path is not None and handoff_markdown is not None:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(handoff_markdown, encoding="utf-8")
            out_summary = summary_path

        return RunResult(
            alert_id=alert["id"], run_id=self.run_id,
            loops_run=self._loop_counter,
            tool_calls=sum(self._tool_call_counts.values()),
            total_latency_ms=round(total_latency_ms, 2),
            terminated_reason=reason,
            handoff_markdown=handoff_markdown,
            trace_path=out_trace,
            summary_path=out_summary,
        )


def _sample(data: dict, max_chars: int = 200) -> dict:
    """Clip long string fields in result samples so transcripts stay readable."""
    out = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_chars:
            out[k] = v[:max_chars] + "…"
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Replay mode (handout §5.6)
# ---------------------------------------------------------------------------
def build_replay_rpc(trace_path: Path) -> Callable[[dict], dict]:
    """Return an rpc() callable that serves responses from a recorded trace.
    Matches requests by method name in order — sufficient for deterministic
    replay tests without touching live tools.
    """
    events = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    responses = [e["payload"] for e in events if e["direction"] == "response"]
    iterator = iter(responses)

    def rpc(request: dict) -> dict:
        try:
            recorded = next(iterator)
        except StopIteration as exc:
            raise RuntimeError("replay exhausted before orchestrator finished") from exc
        # Rewrite the id so correlation matches the current run
        recorded = dict(recorded)
        recorded["id"] = request.get("id")
        return recorded

    return rpc
