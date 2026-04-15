# Incident ALRT-2025-07 — handoff summary

## Evidence collected (3 items)
- Retrieved 2 runbook(s): CrashLoopBackoff pods, High CPU on API nodes
- Diagnostic `kubectl top pods` on staging-api: CPU hot on both api pods (~93%); matches the alert.
- Diagnostic `kubectl get events` on staging-api: BackoffLimitExceeded on api-7f9c in the last 2 minutes.

## Recommended actions
- Follow RB-001 (restart API service) if CPU remains above threshold.
- Open a ticket with the on-call platform engineer and attach the replay trace.