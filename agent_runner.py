import os
import json
import shutil
from datetime import datetime
from context_manager import (
    load_memory,
    save_memory_context,
    get_current_goal,
    record_last_result,
    add_failure_pattern,
    get_next_step,
    add_next_step,
    track_confirmed,
    track_rejected,
)
from task_executor import execute_task
from drive_uploader import upload_log_to_drive

MEMORY_PATH = "context.json"
LOG_DIR = "logs"
TEST_SUITE_FILE = "test_suite.json"
AGENT_CORE_FILES = ["agent_runner.py", "context_manager.py", "task_executor.py", "app.py"]

os.makedirs(LOG_DIR, exist_ok=True)

def run_agent(input_data):
    memory = load_memory()

    # === NEW INTENT HANDLER: queue_task ===
    if input_data.get("intent") == "queue_task":
        task = input_data.get("task")
        if not task:
            return {"success": False, "error": "Missing 'task' for queue_task intent."}
        add_next_step(memory, task)
        save_memory_context(memory)
        return {
            "success": True,
            "message": "✅ Task added to queue.",
            "queued_task": task,
            "memory_snapshot": memory.get("next_steps", [])
        }

    # === Phase 4.6: Execution + fallback planning ===
    plan = input_data.get("executionPlanned") or input_data.get("plan") or input_data.get("task") or input_data

    fallback_used = False
    if "action" not in plan and "intent" in input_data:
        plan["action"] = input_data["intent"]
        fallback_used = True

    result = execute_task(plan)
    record_last_result(memory, plan, result, fallback_used)

    if not result.get("success"):
        task_summary = f"[{plan.get('intent') or plan.get('action')}] {plan.get('filename', '')} – {plan.get('notes', '')}".strip()
        add_failure_pattern(memory, {"task": task_summary, "result": result})

    save_memory_context(memory)

    # PATCH: log filename includes timestamp formatted for later confirmation
    timestamp = datetime.utcnow().isoformat()
    task_id = timestamp.replace(":", "_").replace(".", "_")
    log_filename = f"log-{task_id}.json"
    log_path = os.path.join(LOG_DIR, log_filename)

    with open(log_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "input": input_data,
            "execution": plan,
            "result": result,
            "memory": memory
        }, f, indent=2)

    subfolder = datetime.utcnow().strftime("%Y-%m-%d")
    upload_log_to_drive(log_path, subfolder)

    return {
        "result": result,
        "executionPlanned": plan,
        "fallbackUsed": fallback_used,
        "memory": memory,
        "roadmap": {
            "currentPhase": "Phase 4.6",
            "nextPhase": "Phase 4.7 – External Tools + Test Suites",
            "subgoal": "Enable self-awareness and task parallelism tracking."
        },
        "overallGoal": get_current_goal(memory),
        "phase": "Phase 4.6 – Self Awareness and Parallelism",
        "timestamp": timestamp
    }

def run_and_log_task(memory, task):
    result = execute_task(task)
    record_last_result(memory, task, result)

    if not result.get("success"):
        summary = f"[{task.get('intent') or task.get('action')}] {task.get('filename', '')} – {task.get('notes', '')}".strip()
        add_failure_pattern(memory, {"task": summary, "result": result})

    save_memory_context(memory)

    # PATCH: log filename includes timestamp formatted for later confirmation
    timestamp = datetime.utcnow().isoformat()
    task_id = timestamp.replace(":", "_").replace(".", "_")
    log_filename = f"log-{task_id}.json"
    log_path = os.path.join(LOG_DIR, log_filename)

    with open(log_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "execution": task,
            "result": result,
            "memory": memory
        }, f, indent=2)

    subfolder = datetime.utcnow().strftime("%Y-%m-%d")
    upload_log_to_drive(log_path, subfolder)

    return result

def run_next():
    memory = load_memory()
    task = get_next_step(memory)
    if not task:
        return {"error": "⚠️ No queued tasks in memory."}

    result = run_and_log_task(memory, task)

    return {
        "message": "✅ Ran next task from memory queue.",
        "task": task,
        "result": result
    }

def run_tests_from_file():
    memory = load_memory()

    if not os.path.exists(TEST_SUITE_FILE):
        return {"error": "No test_suite.json found."}

    with open(TEST_SUITE_FILE, "r") as f:
        test_suite = json.load(f)

    test_results = []
    for i, test in enumerate(test_suite):
        result = execute_task(test)
        passed = result.get("success", False)
        test_results.append({
            "index": i,
            "test": test,
            "passed": passed,
            "result": result
        })

        record_last_result(memory, test, result)

        if not passed:
            add_failure_pattern(memory, {
                "test_index": i,
                "test": test,
                "result": result
            })

    save_memory_context(memory)

    return {
        "message": f"✅ Ran {len(test_results)} tests.",
        "results": test_results
    }

def finalize_task_execution(status, task_info=None):
    memory = load_memory()
    if status == "confirmed":
        track_confirmed(memory)
    elif status == "rejected":
        track_rejected(memory)
        if task_info:
            add_failure_pattern(memory, {"task": task_info})
    save_memory_context(memory)

def modify_self(filename, updated_code):
    backup_name = f"{filename}.bak.{datetime.utcnow().isoformat().replace(':', '_')}"
    shutil.copy(filename, backup_name)
    with open(filename, "w") as f:
        f.write(updated_code)

    memory = load_memory()
    memory["self_edits"].append({
        "filename": filename,
        "backup": backup_name,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_memory_context(memory)

    return {"success": True, "message": f"✅ Modified {filename}, backup saved as {backup_name}"}
