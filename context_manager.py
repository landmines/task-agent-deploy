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
            "deployment_events": [],
            "project_name": "Task Agent",
            "purpose": "Build and manage projects via user or ChatGPT instructions.",
            "next_steps": []
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

def record_last_result(context, task, result, fallback=False):
    update_memory_context(
        context=context,
        task=task,
        intent=task.get("intent") or task.get("action"),
        success=result.get("success", False),
        result=result
    )

def increment_confirmed(context):
    context["confirmed_count"] += 1

def increment_rejected(context):
    context["rejected_count"] += 1

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

def add_failure_pattern(context, pattern):
    context["failure_patterns"].append({
        **pattern,
        "timestamp": datetime.utcnow().isoformat()
    })

    if len(context["failure_patterns"]) > 10:
        context["failure_patterns"] = context["failure_patterns"][-10:]

def update_memory_context(context, task, intent, success, result=None):
    context["last_updated"] = datetime.utcnow().isoformat()
    context["last_result"] = {
        "task": task,
        "intent": intent,
        "status": "success" if success else "fail",
        "timestamp": context["last_updated"],
        "result": result or {}
    }
    context["recent_tasks"].append(context["last_result"])
    if len(context["recent_tasks"]) > 10:
        context["recent_tasks"] = context["recent_tasks"][-10:]
    record_intent_stats(context, intent, success)
    save_memory(context)

def add_next_step(context, step):
    context.setdefault("next_steps", [])
    context["next_steps"].append({
        "step": step,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_memory(context)

def clear_next_steps(context):
    context["next_steps"] = []
    save_memory(context)

def get_next_step(context):
    if not context.get("next_steps"):
        return None
    next_item = context["next_steps"].pop(0)
    context["last_updated"] = datetime.utcnow().isoformat()
    save_memory(context)
    return next_item.get("step", next_item)

def track_confirmed(context):
    increment_confirmed(context)
    save_memory(context)

def track_rejected(context):
    increment_rejected(context)
    save_memory(context)

def log_deployment_event(success, source, note=""):
    context = load_memory()
    context.setdefault("deployment_events", [])
    context["deployment_events"].append({
        "success": success,
        "source": source,
        "note": note,
        "timestamp": datetime.utcnow().isoformat()
    })
    if len(context["deployment_events"]) > 20:
        context["deployment_events"] = context["deployment_events"][-20:]
    save_memory(context)

def summarize_memory(context):
    return {
        "summary": {
            "total_confirmed": context["confirmed_count"],
            "total_rejected": context["rejected_count"],
            "intents": context["intent_stats"],
            "last_task": context["last_result"],
            "queued": context.get("next_steps", []),
        }
    }

def get_current_goal(context):
    if context.get("next_steps"):
        step = context["next_steps"][0].get("step", {})
        return f"Next: {step.get('intent', 'unknown')}"
    return "Idle – no current goal."
