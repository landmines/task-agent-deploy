#!/usr/bin/env python3
import sys
import json

def main():
    # Read the full JSON response from stdin
    data = json.load(sys.stdin)

    # Timestamp
    ts = data.get("timestamp", "")

    # The “plan” section holds your task info under the current API
    plan = data.get("executionPlanned") or data.get("plan") or {}
    intent = plan.get("intent") or plan.get("action") or "<no-intent>"
    fname  = plan.get("filename", "<no-file>")

    # The human‑friendly message returned by the agent
    message = data.get("result", {}).get("message", "<no-msg>")

    # Print one tidy line
    print(f"[{ts}] {intent}: {fname} - {message}")

if __name__ == "__main__":
    main()