"""JSON schemas + minimal validator for MCP tool calls.

Scope: required-key presence and type-match only. Enough to reject malformed
tool calls at the server boundary without pulling in jsonschema.
"""
from __future__ import annotations

TOOL_SCHEMAS: dict[str, dict] = {
    "retrieve_runbook": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 2},
        },
    },
    "run_diagnostic": {
        "type": "object",
        "required": ["command", "host"],
        "properties": {
            "command": {"type": "string"},
            "host": {"type": "string"},
        },
    },
    "summarize_incident": {
        "type": "object",
        "required": ["alert_id", "evidence"],
        "properties": {
            "alert_id": {"type": "string"},
            "evidence": {"type": "array"},
        },
    },
}

_PY_TYPES = {
    "string": str,
    "integer": int,
    "array": list,
    "object": dict,
    "boolean": bool,
    "number": (int, float),
}


def validate(tool: str, args: dict) -> list[str]:
    """Return a list of validation errors (empty if OK)."""
    if tool not in TOOL_SCHEMAS:
        return [f"unknown tool: {tool}"]
    schema = TOOL_SCHEMAS[tool]
    errs: list[str] = []
    for key in schema.get("required", []):
        if key not in args:
            errs.append(f"missing required argument: {key}")
    for key, value in args.items():
        prop = schema["properties"].get(key)
        if prop is None:
            errs.append(f"unexpected argument: {key}")
            continue
        expected = _PY_TYPES.get(prop["type"])
        if expected is not None and not isinstance(value, expected):
            errs.append(f"{key}: expected {prop['type']}, got {type(value).__name__}")
    return errs
