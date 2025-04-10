import json
import os
from datetime import datetime

MEMORY_FILE = "context.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {
            "confirmed_count": 0,
            "rejected_count": 0,
            "created": datetime.utcnow().isoformat(),
            "last_updated": None,
            "last_result": None,
            "recent_tasks": [],
            "failure_patterns": [],
            "intent_stats": {},
            "self_notes": [],
            "task_links": [],
            "self_edits": [],
            "project_name": "Task Agent",
            "purpose": "Build and manage projects via user or ChatGPT instructions."
        }
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(context):
    with open(MEMORY_FILE, "w") as f:
        json.dump(context, f, indent=2)

def load_memory_context():
    return load_memory()

def save_memory_context(context):
    return save_memory(context)

def record_intent_stats(context, intent, success):
    if intent not in context["intent_stats"]:
        context["intent_stats"][intent] = {"success": 0, "fail": 0}
    if success:
        context["intent_stats"][intent]["success"] += 1
    else:
        context["intent_stats"][intent]["fail"] += 1

def append_self_note(context, note):
    context["self_notes"].append({
        "note": note,
        "timestamp": datetime.utcnow().isoformat()
    })

def update_memory(context, log_data):
    intent = (log_data.get("executionPlanned") or {}).get("action", "unknown")
    success = (log_data.get("executionResult") or {}).get("success", False)
    task = log_data.get("taskReceived", "")

    context["last_updated"] = datetime.utcnow().isoformat()
    context["last_result"] = {
        "task": task,
        "intent": intent,
        "status": "success" if success else "fail",
        "timestamp": context["last_updated"]
    }
    context["recent_tasks"].append(context["last_result"])
    if len(context["recent_tasks"]) > 10:
        context["recent_tasks"] = context["recent_tasks"][-10:]
    record_intent_stats(context, intent, success)
    return context

def summarize_memory(context):
    return {
        "summary": {
            "total_confirmed": context["confirmed_count"],
            "total_rejected": context["rejected_count"],
            "intents": context["intent_stats"],
            "last_task": context["last_result"]
        }
    }
