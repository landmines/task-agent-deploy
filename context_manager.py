import json
import os
from datetime import datetime, UTC

MEMORY_FILE = "context.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {
            "confirmed_count": 0,
            "rejected_count": 0,
            "cost_tracking": {
                "total_estimated": 0.0,
                "deployment_costs": [],
                "api_usage_costs": [],
                "last_updated": datetime.now(UTC).isoformat()
            },
            "created": datetime.now(UTC).isoformat(),
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
    context["last_updated"] = datetime.now(UTC).isoformat()
    return save_memory(context)

def get_trust_score(context, intent=None):
    """Calculate trust score based on success history"""
    if intent:
        stats = context.get("intent_stats", {}).get(intent, {})
        success = stats.get("success", 0)
        total = success + stats.get("failure", 0)
        if total < 5:  # Not enough data
            return 0.3  # Conservative default
        return success / total

    confirmed = context.get("confirmed_count", 0)
    total = confirmed + context.get("rejected_count", 0)
    if total < 10:  # Not enough overall data
        return 0.3  # Conservative default
    return confirmed / total

def requires_confirmation(intent, context):
    """Determine if an action needs confirmation"""
    # Always confirm these actions
    if intent in ["delete_file", "deploy", "modify_self"]:
        return True

    # Check trust score
    trust = get_trust_score(context, intent)
    return trust < 0.8 or context.get("always_confirm", False)

def update_trust_metrics(context, intent, success):
    """Update trust metrics after task execution"""
    if intent not in context.get("intent_stats", {}):
        context["intent_stats"][intent] = {"success": 0, "failure": 0}

    if success:
        context["intent_stats"][intent]["success"] += 1
    else:
        context["intent_stats"][intent]["failure"] += 1

    save_memory_context(context)

def requires_confirmation(intent, context):
    """Determine if an action needs confirmation"""
    if intent in ["delete_file", "deploy", "modify_self"]:
        return True
    trust_score = get_trust_score(context, intent)
    return trust_score < 0.8 or context.get("always_confirm", False)

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
        "timestamp": datetime.now(UTC).isoformat()
    })

def add_failure_pattern(context, pattern):
    context["failure_patterns"].append({
        **pattern,
        "timestamp": datetime.now(UTC).isoformat()
    })

    if len(context["failure_patterns"]) > 10:
        context["failure_patterns"] = context["failure_patterns"][-10:]

def update_memory_context(context, task, intent, success, result=None):
    context["last_updated"] = datetime.now(UTC).isoformat()
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
        "timestamp": datetime.now(UTC).isoformat()
    })
    save_memory(context)

def clear_next_steps(context):
    context["next_steps"] = []
    save_memory(context)

def get_next_step(context):
    """Get and remove next task from queue with error handling"""
    try:
        if not context.get("next_steps"):
            return None
        next_item = context["next_steps"].pop(0)
        context["last_updated"] = datetime.now(UTC).isoformat()
        save_memory(context)
        return next_item.get("step") if isinstance(next_item, dict) and "step" in next_item else next_item
    except Exception as e:
        print(f"Error getting next step: {e}")
        return None

def track_confirmed(context):
    """Track a confirmed task execution"""
    context["confirmed_count"] = context.get("confirmed_count", 0) + 1
    save_memory_context(context)

def track_rejected(context):
    """Track a rejected task execution"""
    context["rejected_count"] = context.get("rejected_count", 0) + 1
    save_memory_context(context)


def log_deployment_event(success, source, note="", cost_data=None):
    context = load_memory()
    context.setdefault("deployment_events", [])
    context.setdefault("cost_tracking", {
        "total_estimated": 0.0,
        "deployment_costs": [],
        "api_usage_costs": [],
        "github_costs": [],
        "last_updated": datetime.now(UTC).isoformat()
    })
    
    event = {
        "success": success,
        "source": source,
        "note": note,
        "timestamp": datetime.now(UTC).isoformat(),
        "cost_data": cost_data
    }
    
    if cost_data:
        context["cost_tracking"]["github_costs"].append(cost_data)
        
    context["deployment_events"].append(event)
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

def get_current_goal(memory):
    """Get the current goal from memory"""
    if not memory.get("next_steps"):
        return None
    return memory["next_steps"][0] if memory["next_steps"] else None

def get_next_step(memory):
    """Get and remove next step from queue"""
    if not memory.get("next_steps"):
        return None
    step = memory["next_steps"].pop(0).get("step") if isinstance(memory["next_steps"][0], dict) else memory["next_steps"].pop(0)
    save_memory(memory)
    return step

def track_confirmed(memory):
    """Track confirmed action"""
    memory["confirmed_count"] = memory.get("confirmed_count", 0) + 1
    save_memory(memory)

def track_rejected(memory):
    """Track rejected action"""
    memory["rejected_count"] = memory.get("rejected_count", 0) + 1
    save_memory(memory)

def get_trust_score(memory, intent=None):
    """Calculate trust score for an intent or overall"""
    # Check for trust override settings
    if memory.get("trust_settings", {}).get("force_trust"):
        return 1.0
    if memory.get("trust_settings", {}).get("always_confirm"):
        return 0.0
        
    if intent:
        stats = memory.get("intent_stats", {}).get(intent, {})
        success = stats.get("success", 0)
        total = success + stats.get("failure", 0)
        return (success / total) if total > 5 else 0.0

def update_trust_settings(memory, settings):
    """Update trust and confirmation settings"""
    memory.setdefault("trust_settings", {})
    memory["trust_settings"].update(settings)
    memory["trust_settings"]["last_updated"] = datetime.now(UTC).isoformat()
    
    # Track safety preferences
    memory["trust_settings"].setdefault("safety_preferences", {
        "always_confirm": False,
        "force_trust": False,
        "auto_rollback": True,
        "failure_threshold": 3
    })
    
    save_memory_context(memory)
    return memory["trust_settings"]

def check_failure_patterns(memory, task_result):
    """Check if task needs automatic rollback"""
    if not task_result.get("success"):
        patterns = memory.get("failure_patterns", [])
        recent_failures = [p for p in patterns 
                         if p.get("timestamp", "") > 
                         (datetime.now(UTC) - timedelta(hours=1)).isoformat()]
        
        if len(recent_failures) >= memory.get("trust_settings", {}).get("safety_preferences", {}).get("failure_threshold", 3):
            return True
    return False

    confirmed = memory.get("confirmed_count", 0)
    rejected = memory.get("rejected_count", 0)
    total = confirmed + rejected
    return (confirmed / total) if total > 5 else 0.0

def get_current_goal(context):
    if context.get("next_steps"):
        step = context["next_steps"][0].get("step", {})
        return f"Next: {step.get('intent', 'unknown')}"
    return "Idle – no current goal."