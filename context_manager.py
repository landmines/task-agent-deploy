import os
import json
from datetime import datetime

MEMORY_FILE = "memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return initialize_memory()
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load memory: {e}")
        return initialize_memory()

def save_memory(memory):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=2)
        print("✅ Memory saved.")
    except Exception as e:
        print(f"❌ Failed to save memory: {e}")

def initialize_memory():
    return {
        "created": datetime.utcnow().isoformat(),
        "last_updated": None,
        "project_name": "Task Agent",
        "purpose": "Build and manage projects via user or ChatGPT instructions.",
        "recent_tasks": [],
        "last_result": None,
        "confirmed_count": 0,
        "rejected_count": 0,
        "failure_patterns": [],
        "notes": []
    }

def update_memory(memory, task_result):
    memory["last_updated"] = datetime.utcnow().isoformat()

    # Track result of last task
    memory["last_result"] = {
        "timestamp": memory["last_updated"],
        "task": task_result.get("taskReceived"),
        "status": task_result.get("executionResult", {}),
        "intent": task_result.get("executionPlanned", {}).get("action", "unknown")
    }

    # Append recent task
    memory["recent_tasks"] = (memory.get("recent_tasks") or [])[-9:]  # keep last 10
    memory["recent_tasks"].append(memory["last_result"])

    # Track confirmation
    if task_result.get("confirmationNeeded") is False:
        memory["confirmed_count"] += 1
    if "rejected" in str(task_result).lower():
        memory["rejected_count"] += 1

    return memory