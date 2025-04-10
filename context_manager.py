import json
import os
from datetime import datetime

MEMORY_FILE = "context.json"

# Load memory context from file or initialize fresh
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

# Aliases for compatibility
def load_memory_context():
    return load_memory()

def save_memory_context(context):
    return save_memory(context)

# Save memory context to file
def save_memory(context):
    with open(MEMORY_FILE, "w") as f:
        json.dump(context, f, indent=2)

# Record outcome of confirmed task
def record_intent_stats(context, intent, success):
    if intent not in context["intent_stats"]:
        context["intent_stats"][intent] = {"success": 0, "fail": 0}
    if success:
        context["intent_stats"][intent]["success"] += 1
    else:
        context["intent_stats"][intent]["fail"] += 1

# Append strategic insight or learning note
def append_self_note(context, note):
    context["self_notes"].append({
        "note": note,
        "timestamp": datetime.utcnow().isoformat()
    })

# Update memory after any task (used by finalize_task_execution or agent directly)
def update_memory_context(context, task, intent, success):
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
    save_memory(context)

# Used by confirm route to finalize confirmed task result
def finalize_task_execution(task, intent, success, result=None):
    context = load_memory()
    context["confirmed_count"] += 1
    update_memory_context(context, task, intent, success)
    save_memory(context)
