#!/usr/bin/env python3
import sys, json

# Read the full JSON object from stdin
data = json.load(sys.stdin)

# Pull out the bits we care about
ts      = data.get("timestamp", "")
task    = data.get("task", {}) or {}
intent  = task.get("intent", "<no-intent>")
fname   = task.get("filename", "<no-file>")
message = data.get("result", {}).get("message", "")

# Print one tidy line
print(f"[{ts}] {intent}: {fname} – {message}")