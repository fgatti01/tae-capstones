"""Integration test: full Observe→Plan→Act→Learn loop + replay (§5.7.2)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from incident_agent.memory import MemoryStore
from incident_agent.server import IncidentMCPServer
from incident_agent.orchestrator import (
    IncidentOrchestrator, Budgets, build_replay_rpc,
)


ALERT = {
    "id": "ALRT-2025-07", "service": "staging-api",
    "symptom": "CPU spike on node-3 causing pod crashloop", "severity": "high",
}


def _budgets():
    return Budgets(max_loops=4, max_latency_ms=2000, max_tool_calls=8,
                   max_per_tool={"run_diagnostic": 3, "retrieve_runbook": 3,
                                 "summarize_incident": 2})


def _run_once(tmp_path: Path, run_id: str = "it"):
    memory = MemoryStore()
    server = IncidentMCPServer(memory=memory)
    orch = IncidentOrchestrator(rpc=server.handle, memory=memory,
                                budgets=_budgets(),
                                logger=logging.getLogger("test"), run_id=run_id)
    return orch.run(
        alert=dict(ALERT),
        trace_path=tmp_path / "trace.jsonl",
        summary_path=tmp_path / "summary.md",
    )


def test_full_loop_produces_handoff(tmp_path):
    result = _run_once(tmp_path)
    assert result.handoff_markdown is not None, "no handoff summary produced"
    assert result.loops_run >= 2, "handout requires at least two full loops"
    assert result.tool_calls >= 3


def test_loop_invokes_retrieval_and_diagnostics(tmp_path):
    result = _run_once(tmp_path)
    # Handout §5.7.2 assertions.
    tools_used = {d.action for d in _read_memory_from_trace(result.trace_path)}
    assert "retrieve_runbook" in tools_used, "expected at least one runbook retrieval"
    assert "run_diagnostic" in tools_used, "expected at least one diagnostic call"
    assert "summarize_incident" in tools_used, "expected a final summary"


def test_handoff_references_evidence_and_recommendations(tmp_path):
    result = _run_once(tmp_path)
    md = result.handoff_markdown
    assert "Recommended actions" in md
    assert "Evidence collected" in md
    # The summary should cite at least one diagnostic outcome by substring.
    assert "kubectl" in md or "RB-001" in md


def test_correlation_ids_are_unique(tmp_path):
    result = _run_once(tmp_path, run_id="uniq")
    lines = result.trace_path.read_text().splitlines()
    events = [json.loads(l) for l in lines]
    # Every pair of (request, response) must share the same correlation id;
    # requests themselves must use distinct correlation ids.
    req_cids = [e["correlation_id"] for e in events if e["direction"] == "request"]
    assert len(req_cids) == len(set(req_cids)), "duplicate correlation IDs in requests"


def test_budget_latency_aborts_loop(tmp_path):
    memory = MemoryStore()
    server = IncidentMCPServer(memory=memory)
    budgets = Budgets(max_loops=10, max_latency_ms=0, max_tool_calls=50,
                      max_per_tool={})
    orch = IncidentOrchestrator(rpc=server.handle, memory=memory, budgets=budgets,
                                logger=logging.getLogger("test"), run_id="budget")
    result = orch.run(alert=dict(ALERT))
    assert "max_latency_ms" in result.terminated_reason


def test_replay_is_deterministic(tmp_path):
    first = _run_once(tmp_path, run_id="first")
    rpc = build_replay_rpc(first.trace_path)
    memory = MemoryStore()
    orch = IncidentOrchestrator(rpc=rpc, memory=memory, budgets=_budgets(),
                                logger=logging.getLogger("test"), run_id="replay")
    second = orch.run(alert=dict(ALERT))
    assert second.handoff_markdown == first.handoff_markdown, \
        "replay must reproduce the original handoff bit-for-bit"
    assert second.loops_run == first.loops_run
    assert second.tool_calls == first.tool_calls


def _read_memory_from_trace(trace_path: Path):
    """Extract the sequence of tool calls from a transcript for assertions."""
    from incident_agent.memory import MemoryDelta
    events = [json.loads(l) for l in trace_path.read_text().splitlines()]
    out = []
    for e in events:
        if e["direction"] != "request":
            continue
        p = e["payload"]
        if p.get("method") == "callTool":
            name = p["params"]["name"]
            out.append(MemoryDelta.new(
                alert_id="-", correlation_id=e["correlation_id"], phase="act",
                action=name, payload=p["params"]["arguments"],
                result_summary="", latency_ms=0.0,
            ))
    return out
