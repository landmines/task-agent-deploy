#!/usr/bin/env python3
import sys, json

data    = json.load(sys.stdin)
ts      = data.get("timestamp", "")
task    = data.get("task", {}) or {}
intent  = task.get("intent","<no‑intent>")
fname   = task.get("filename","<no‑file>")
message = data.get("result",{}).get("message","<no‑msg>")

print(f"[{ts}] {intent:12} {fname:20} → {message}")