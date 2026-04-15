"""MCP server — tool handlers, resource surface, and JSON-RPC 2.0 dispatch.

Handout §5.3 requirements: capability endpoint, validated tool handlers with
structured output (status, data, metrics), and per-request logging hooks.

Three tools + one resource:
  - retrieve_runbook(query, top_k)              : keyword search over runbooks
  - run_diagnostic(command, host)               : canned sandboxed diagnostics
  - summarize_incident(alert_id, evidence)      : deterministic summary
  - memory://alerts/latest                      : latest alert + memory deltas
"""
from __future__ import annotations

import time
from typing import Any, Callable

from .schemas import TOOL_SCHEMAS, validate
from .memory import MemoryStore


RUNBOOKS: list[dict] = [
    {
        "id": "RB-001",
        "title": "High CPU on API nodes",
        "body": "Restart the service if CPU stays above 90% for 5 minutes. "
                "Check for runaway worker threads before the restart.",
        "tags": ["cpu", "api", "restart"],
    },
    {
        "id": "RB-002",
        "title": "CrashLoopBackoff pods",
        "body": "If pods crashloop, capture logs before redeploying. "
                "Inspect OOMKilled status; consider bumping memory limit.",
        "tags": ["crashloop", "pods", "logs", "oom"],
    },
    {
        "id": "RB-003",
        "title": "Database connection spike",
        "body": "Check pg_stat_activity for long-running transactions. "
                "Terminate idle-in-transaction sessions older than 10 min.",
        "tags": ["database", "postgres", "connections"],
    },
    {
        "id": "RB-004",
        "title": "Failed deployment rollback",
        "body": "Roll back to the previous ReplicaSet. Verify readiness probes "
                "pass on the restored version before re-enabling traffic.",
        "tags": ["deployment", "rollback", "kubernetes"],
    },
]


# Canned diagnostic stub: deterministic outputs keyed by (command, host).
# Keeps the capstone hermetic and replayable without a live cluster.
DIAGNOSTICS: dict[tuple[str, str], dict] = {
    ("kubectl top pods", "staging-api"): {
        "stdout": "NAME           CPU(cores)   MEMORY(bytes)\napi-7f9c   920m         512Mi\napi-9d4e   940m         498Mi",
        "stderr": "",
        "exit_code": 0,
        "summary": "CPU hot on both api pods (~93%); matches the alert.",
    },
    ("kubectl get events", "staging-api"): {
        "stdout": "LAST SEEN  TYPE     REASON            OBJECT\n2m         Warning  BackoffLimitExceeded pod/api-7f9c",
        "stderr": "",
        "exit_code": 0,
        "summary": "BackoffLimitExceeded on api-7f9c in the last 2 minutes.",
    },
}


def _handle_retrieve_runbook(args: dict) -> dict:
    query = args["query"].lower()
    top_k = args.get("top_k", 2)
    scored = []
    for rb in RUNBOOKS:
        score = sum(1 for tag in rb["tags"] if tag in query)
        score += sum(1 for word in query.split() if word in rb["body"].lower())
        if score > 0:
            scored.append((score, rb))
    scored.sort(key=lambda t: -t[0])
    hits = [{"id": rb["id"], "title": rb["title"], "body": rb["body"], "score": s}
            for s, rb in scored[:top_k]]
    return {"query": query, "hits": hits}


def _handle_run_diagnostic(args: dict) -> dict:
    key = (args["command"], args["host"])
    canned = DIAGNOSTICS.get(key)
    if canned is None:
        return {
            "command": args["command"], "host": args["host"],
            "stdout": "", "stderr": f"no canned diagnostic for {key}",
            "exit_code": 2, "summary": "no diagnostic available",
        }
    return {"command": args["command"], "host": args["host"], **canned}


def _handle_summarize_incident(args: dict) -> dict:
    alert_id = args["alert_id"]
    evidence = args["evidence"]
    bullet_points = [f"- {e}" for e in evidence]
    summary = (
        f"# Incident {alert_id} — handoff summary\n\n"
        f"## Evidence collected ({len(evidence)} items)\n"
        + "\n".join(bullet_points)
        + "\n\n## Recommended actions\n"
        f"- Follow RB-001 (restart API service) if CPU remains above threshold.\n"
        f"- Open a ticket with the on-call platform engineer and attach the replay trace."
    )
    return {"alert_id": alert_id, "summary_markdown": summary, "n_items": len(evidence)}


HANDLERS: dict[str, Callable[[dict], dict]] = {
    "retrieve_runbook": _handle_retrieve_runbook,
    "run_diagnostic": _handle_run_diagnostic,
    "summarize_incident": _handle_summarize_incident,
}


class IncidentMCPServer:
    """JSON-RPC 2.0 dispatch. Transport-agnostic: call `handle(request)` with
    a parsed JSON payload and it returns a dict ready to be serialized back.
    """
    def __init__(self, memory: MemoryStore, request_log: list | None = None):
        self.memory = memory
        self.request_log = request_log if request_log is not None else []
        self.capabilities = {
            "tools": [
                {"name": name, "description": f"See schema for {name}.", "schema": schema,
                 "cost_hint_ms": {"retrieve_runbook": 20, "run_diagnostic": 40,
                                  "summarize_incident": 15}[name]}
                for name, schema in TOOL_SCHEMAS.items()
            ],
            "resources": [{"uri": "memory://alerts/latest",
                           "description": "Latest alert + recent memory deltas"}],
        }

    def handle(self, request: dict) -> dict:
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {}) or {}
        t0 = time.perf_counter()
        try:
            if method == "initialize":
                result: dict[str, Any] = {"capabilities": self.capabilities}
            elif method == "getResource":
                uri = params.get("uri", "")
                if uri != "memory://alerts/latest":
                    return self._error(req_id, -32602, f"unknown resource uri: {uri}")
                result = {"uri": uri, "data": self.memory.latest_snapshot(params.get("alert_id"))}
            elif method == "callTool":
                name = params.get("name")
                args = params.get("arguments", {}) or {}
                errs = validate(name, args)
                if errs:
                    return self._error(req_id, -32602, "schema validation failed",
                                       data={"errors": errs})
                handler = HANDLERS[name]
                t_tool = time.perf_counter()
                data = handler(args)
                latency_ms = (time.perf_counter() - t_tool) * 1000
                result = {
                    "status": "ok",
                    "data": data,
                    "metrics": {"latency_ms": round(latency_ms, 4)},
                }
            else:
                return self._error(req_id, -32601, f"unknown method: {method}")
        except Exception as exc:  # defensive; reported back as JSON-RPC error
            return self._error(req_id, -32603, f"internal error: {exc!r}")
        response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        self.request_log.append({"request": request, "response": response,
                                 "server_latency_ms": round((time.perf_counter() - t0) * 1000, 4)})
        return response

    @staticmethod
    def _error(req_id, code: int, message: str, data: dict | None = None) -> dict:
        err: dict = {"code": code, "message": message}
        if data:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": req_id, "error": err}
