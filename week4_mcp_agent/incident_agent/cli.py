"""CLI for the Incident Command Agent.

Subcommands:
  run-demo            end-to-end incident loop against the in-process MCP server
  replay <trace>      deterministic replay of a stored trace (no live tools)
  show-capabilities   print the server's capability advertisement as JSON
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .memory import MemoryStore
from .server import IncidentMCPServer
from .orchestrator import IncidentOrchestrator, Budgets, build_replay_rpc


HERE = Path(__file__).resolve().parent.parent
ARTIFACTS = HERE / "artifacts"


def _demo_alert() -> dict:
    # Mirrors the ALERT_PAYLOAD in the handout §6 reference server.
    return {
        "id": "ALRT-2025-07",
        "service": "staging-api",
        "symptom": "CPU spike on node-3 causing pod crashloop",
        "severity": "high",
    }


def _budgets() -> Budgets:
    return Budgets(
        max_loops=4, max_latency_ms=2000, max_tool_calls=8,
        max_per_tool={"run_diagnostic": 3, "retrieve_runbook": 3, "summarize_incident": 2},
    )


def _make_logger(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    return logging.getLogger("incident_agent")


def cmd_run_demo(args: argparse.Namespace) -> int:
    log = _make_logger(args.log_level)
    memory = MemoryStore()
    server = IncidentMCPServer(memory=memory)
    orch = IncidentOrchestrator(rpc=server.handle, memory=memory,
                                budgets=_budgets(), logger=log, run_id=args.run_id)
    result = orch.run(
        alert=_demo_alert(),
        trace_path=ARTIFACTS / "sample_trace.jsonl",
        summary_path=ARTIFACTS / "sample_summary.md",
    )
    print(json.dumps({
        "alert_id": result.alert_id,
        "run_id": result.run_id,
        "loops_run": result.loops_run,
        "tool_calls": result.tool_calls,
        "total_latency_ms": result.total_latency_ms,
        "terminated_reason": result.terminated_reason,
        "trace_path": str(result.trace_path) if result.trace_path else None,
        "summary_path": str(result.summary_path) if result.summary_path else None,
    }, indent=2))
    return 0 if result.handoff_markdown else 1


def cmd_replay(args: argparse.Namespace) -> int:
    log = _make_logger(args.log_level)
    memory = MemoryStore()
    rpc = build_replay_rpc(Path(args.trace))
    orch = IncidentOrchestrator(rpc=rpc, memory=memory, budgets=_budgets(),
                                logger=log, run_id=f"replay-{args.run_id}")
    result = orch.run(alert=_demo_alert())
    print(json.dumps({
        "replayed_from": args.trace,
        "loops_run": result.loops_run,
        "tool_calls": result.tool_calls,
        "terminated_reason": result.terminated_reason,
        "produced_handoff": bool(result.handoff_markdown),
    }, indent=2))
    return 0 if result.handoff_markdown else 1


def cmd_show_capabilities(args: argparse.Namespace) -> int:
    server = IncidentMCPServer(memory=MemoryStore())
    resp = server.handle({"jsonrpc": "2.0", "id": "1", "method": "initialize",
                          "params": {"clientName": "cli", "clientVersion": "0.1.0"}})
    print(json.dumps(resp["result"]["capabilities"], indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incident Command Agent CLI")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("run-demo", help="run the full OPAL loop end-to-end")
    p_demo.add_argument("--run-id", default="demo")
    p_demo.set_defaults(func=cmd_run_demo)

    p_replay = sub.add_parser("replay", help="replay a stored trace")
    p_replay.add_argument("trace", help="path to a .jsonl trace produced by run-demo")
    p_replay.add_argument("--run-id", default="1")
    p_replay.set_defaults(func=cmd_replay)

    p_caps = sub.add_parser("show-capabilities", help="print advertised tools/resources")
    p_caps.set_defaults(func=cmd_show_capabilities)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
