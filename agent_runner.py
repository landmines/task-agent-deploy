import os
import json
import shutil
from datetime import datetime, UTC
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
LOG_DIR = os.path.abspath("logs")
RENDER_LOG_FILE = "render.log"
TEST_SUITE_FILE = "test_suite.json"
AGENT_CORE_FILES = ["agent_runner.py", "context_manager.py", "task_executor.py", "app.py"]

os.makedirs(LOG_DIR, exist_ok=True)


def run_agent(input_data):
    memory = load_memory()

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

    # ✅ Unified timestamp for taskId and log
    timestamp = datetime.now(UTC).isoformat()
    task_id = timestamp.replace(":", "_").replace(".", "_")
    log_filename = f"log-{task_id}.json"
    log_path = os.path.join(LOG_DIR, log_filename)
    subfolder = timestamp[:10]

    plan = input_data.get("executionPlanned") or input_data.get("plan") or input_data.get("task") or input_data
    fallback_used = False
    if "action" not in plan and "intent" in input_data:
        plan["action"] = input_data["intent"]
        fallback_used = True

    # ✅ Handle confirmable tasks
    if plan.get("confirmationNeeded"):
        result = {
            "success": True,
            "message": "⏸️ Task logged but awaiting user confirmation.",
            "pending": True,
            "confirmationNeeded": True
        }

        try:
            print(f"🧪 Writing confirmable log to path: {log_path}")
            with open(log_path, "w") as f:
                json.dump({
                    "timestamp": timestamp,
                    "taskId": task_id,
                    "log_filename": log_filename,
                    "input": input_data,
                    "execution": plan,
                    "result": result,
                    "memory": memory
                }, f, indent=2)
            print(f"✅ Confirmable task log written locally: {log_filename}")
        except Exception as e:
            print(f"❌ Failed to write confirmable task log: {e}")

        upload_log_to_drive(log_path, subfolder)
        record_last_result(memory, plan, result)
        save_memory_context(memory)

        print("🧪 Finished returning confirmable response")
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
            "timestamp": timestamp,
            "taskId": task_id,
            "log_filename": log_filename
        }

    result = execute_task(plan)
    record_last_result(memory, plan, result, fallback_used)

    if not result.get("success"):
        task_summary = f"[{plan.get('intent') or plan.get('action')}] {plan.get('filename', '')} – {plan.get('notes', '')}".strip()
        add_failure_pattern(memory, {"task": task_summary, "result": result})

    save_memory_context(memory)

    try:
        with open(log_path, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "taskId": task_id,
                "log_filename": log_filename,
                "input": input_data,
                "execution": plan,
                "result": result,
                "memory": memory
            }, f, indent=2)
        print(f"✅ Log file written: {log_filename}")
    except Exception as e:
        print(f"❌ Failed to write log file: {e}")
        print("📁 Verifying file presence at:", log_path)
        print("📂 Logs directory contains:", os.listdir(LOG_DIR))


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
        "timestamp": timestamp,
        "taskId": task_id,
        "log_filename": log_filename
    }


def run_and_log_task(memory, task):
    # ✅ Unified timestamp for taskId and log
    timestamp = datetime.now(UTC).isoformat()
    task_id = timestamp.replace(":", "_").replace(".", "_")
    log_filename = f"log-{task_id}.json"
    log_path = os.path.join(LOG_DIR, log_filename)
    subfolder = timestamp[:10]

    result = execute_task(task)
    record_last_result(memory, task, result)

    if not result.get("success"):
        summary = f"[{task.get('intent') or task.get('action')}] {task.get('filename', '')} – {task.get('notes', '')}".strip()
        add_failure_pattern(memory, {"task": summary, "result": result})

    save_memory_context(memory)

    try:
        with open(log_path, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "taskId": task_id,
                "log_filename": log_filename,
                "input": task,
                "execution": task,
                "result": result,
                "memory": memory
            }, f, indent=2)
        print(f"✅ Task log saved: {log_filename}")
    except Exception as e:
        print(f"❌ Error saving task log: {e}")

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
            action = task_info.get("execution", {}).get("action") \
                     or task_info.get("execution", {}).get("intent") \
                     or task_info.get("input", {}).get("intent") \
                     or "unknown task"
            add_failure_pattern(memory, {"task": f"{action} – Rejected by user"})
    save_memory_context(memory)


def modify_self(filename, updated_code):
    backup_name = f"{filename}.bak.{datetime.now(UTC).isoformat().replace(':', '_')}"
    shutil.copy(filename, backup_name)
    with open(filename, "w") as f:
        f.write(updated_code)

    memory = load_memory()
    memory["self_edits"].append({
        "filename": filename,
        "backup": backup_name,
        "timestamp": datetime.now(UTC).isoformat()
    })
    save_memory_context(memory)

    return {"success": True, "message": f"✅ Modified {filename}, backup saved as {backup_name}"}