"""Unit tests for each MCP tool handler with golden inputs/outputs (§5.7.1)."""
from __future__ import annotations

import pytest

from incident_agent.memory import MemoryStore
from incident_agent.schemas import validate
from incident_agent.server import IncidentMCPServer


@pytest.fixture
def server():
    return IncidentMCPServer(memory=MemoryStore())


def _call(server: IncidentMCPServer, name: str, args: dict, req_id: str = "t1") -> dict:
    return server.handle({
        "jsonrpc": "2.0", "id": req_id, "method": "callTool",
        "params": {"name": name, "arguments": args},
    })


# ---- Schema validation ----------------------------------------------------

def test_schema_rejects_missing_required():
    errs = validate("run_diagnostic", {"command": "ls"})  # missing host
    assert any("host" in e for e in errs)


def test_schema_rejects_wrong_type():
    errs = validate("retrieve_runbook", {"query": 123})
    assert any("query" in e and "string" in e for e in errs)


def test_schema_accepts_well_formed_args():
    assert validate("retrieve_runbook", {"query": "cpu", "top_k": 2}) == []


# ---- retrieve_runbook -----------------------------------------------------

def test_retrieve_runbook_finds_cpu_guidance(server):
    resp = _call(server, "retrieve_runbook", {"query": "cpu api", "top_k": 2})
    assert "result" in resp
    data = resp["result"]["data"]
    assert len(data["hits"]) >= 1
    # RB-001 is specifically about high CPU on API nodes.
    assert any(h["id"] == "RB-001" for h in data["hits"])
    assert resp["result"]["metrics"]["latency_ms"] >= 0


def test_retrieve_runbook_returns_empty_on_miss(server):
    resp = _call(server, "retrieve_runbook", {"query": "zxzxzx", "top_k": 2})
    assert resp["result"]["data"]["hits"] == []


# ---- run_diagnostic -------------------------------------------------------

def test_run_diagnostic_canned(server):
    resp = _call(server, "run_diagnostic",
                 {"command": "kubectl top pods", "host": "staging-api"})
    d = resp["result"]["data"]
    assert d["exit_code"] == 0
    assert "CPU" in d["stdout"]
    assert "~93%" in d["summary"] or "93" in d["summary"]


def test_run_diagnostic_unknown_returns_status(server):
    resp = _call(server, "run_diagnostic",
                 {"command": "echo hi", "host": "staging-api"})
    d = resp["result"]["data"]
    assert d["exit_code"] == 2
    assert "no diagnostic" in d["summary"]


# ---- summarize_incident ---------------------------------------------------

def test_summarize_incident_structure(server):
    resp = _call(server, "summarize_incident",
                 {"alert_id": "ALRT-1", "evidence": ["fact A", "fact B"]})
    d = resp["result"]["data"]
    assert d["n_items"] == 2
    assert "ALRT-1" in d["summary_markdown"]
    assert "Evidence collected" in d["summary_markdown"]
    assert "Recommended actions" in d["summary_markdown"]


# ---- JSON-RPC error paths -------------------------------------------------

def test_callTool_validation_error_propagates(server):
    resp = _call(server, "run_diagnostic", {"command": "ls"})  # missing host
    assert "error" in resp
    assert resp["error"]["code"] == -32602


def test_unknown_method(server):
    resp = server.handle({"jsonrpc": "2.0", "id": "x", "method": "nope", "params": {}})
    assert resp["error"]["code"] == -32601


def test_unknown_resource_uri(server):
    resp = server.handle({"jsonrpc": "2.0", "id": "y", "method": "getResource",
                          "params": {"uri": "memory://bogus"}})
    assert resp["error"]["code"] == -32602


# ---- Capabilities advertisement -------------------------------------------

def test_initialize_advertises_three_tools_and_one_resource(server):
    resp = server.handle({"jsonrpc": "2.0", "id": "i", "method": "initialize",
                          "params": {}})
    caps = resp["result"]["capabilities"]
    tool_names = {t["name"] for t in caps["tools"]}
    assert tool_names == {"retrieve_runbook", "run_diagnostic", "summarize_incident"}
    assert len(caps["resources"]) >= 1
    assert caps["resources"][0]["uri"] == "memory://alerts/latest"
