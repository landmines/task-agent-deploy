import os
import json
import shutil
from task_executor import execute_task
from drive_uploader import upload_log_to_drive
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

def get_trust_score(memory: dict, intent: str) -> float:
    """Calculate trust score based on past performance"""
    if not intent:
        return 0.5  # Default moderate trust

    stats = memory.get("intent_stats", {}).get(intent, {})
    successes = stats.get("success", 0)
    failures = stats.get("failure", 0)

    if successes + failures == 0:
        return 0.5

    return successes / (successes + failures)

MEMORY_PATH = "context.json"
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
RENDER_LOG_FILE = "render.log"
TEST_SUITE_FILE = "test_suite.json"
AGENT_CORE_FILES = [
    "agent_runner.py", "context_manager.py", "task_executor.py", "app.py"
]

def requires_confirmation(intent: str, memory: dict) -> bool:
    """
    Determine whether the given intent needs user confirmation.
    """
    # No confirmation for safe file operations
    if intent in ["create_file", "append_to_file", "replace_line", "insert_below"]:
        return False

    # High‑risk actions: only skip confirmation if our trust is very high
    high_risk = ["delete_file", "deploy", "modify_self"]
    if intent in high_risk:
        return get_trust_score(memory, intent) < 0.9

    # If the user has globally requested always‑confirm, obey
    if memory.get("always_confirm", False):
        return True

    # Default threshold for everything else
    return get_trust_score(memory, intent) < 0.8

def run_agent(input_data):
    # Ensure logs directory exists
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    memory = load_memory()

    # Track execution metadata
    execution_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    memory["current_execution"] = execution_id

    # Handle planning requests
    if input_data.get("intent") == "plan_tasks" or input_data.get("goal"):
        from planner import plan_tasks, validate_plan
        goal = input_data.get("goal") or input_data.get("task")
        plan = plan_tasks(goal)

        if not validate_plan(plan):
            return {"success": False, "error": "Invalid plan structure"}

        memory["next_steps"] = [{
            "step": step,
            "timestamp": datetime.now(UTC).isoformat()
        } for step in plan]
        save_memory_context(memory)

        return {
            "success": True,
            "message": f"✅ Created plan with {len(plan)} steps",
            "plan": plan,
            "next_steps": memory["next_steps"]
        }

    # Check if confirmation needed based on trust
    intent = input_data.get("intent")
    if intent:
        trust_score = get_trust_score(memory, intent)
        needs_confirmation = requires_confirmation(intent, memory)

        # Skip confirmation for highly trusted actions
        if trust_score >= 0.9 and not needs_confirmation:
            input_data["confirmationNeeded"] = False
        else:
            input_data["confirmationNeeded"] = True

        # Record decision metrics
        memory["confirmation_decisions"] = memory.get("confirmation_decisions", [])
        memory["confirmation_decisions"].append({
            "intent": intent,
            "trust_score": trust_score,
            "confirmation_required": input_data["confirmationNeeded"]
        })

    # Handle special intents
    if input_data.get("intent") == "map_dependencies":
        try:
            from agent_tools.dependency_mapper import run_dependency_mapper
            graph_result = run_dependency_mapper()
            return {
                "success": True,
                "message": "✅ Dependency graph generated.",
                "result": graph_result
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Dependency mapper failed: {str(e)}"
            }

    if input_data.get("intent") == "queue_task":
        task = input_data.get("task")
        if task:
            add_next_step(memory, task)
            save_memory_context(memory)
            return {
                "success": True,
                "message": "Task queued successfully",
                "task": task
            }
        return {
            "success": False,
            "error": "No task provided"
        }

    # ✅ Unified timestamp for taskId and log
    timestamp = datetime.now(UTC).isoformat()
    task_id = timestamp.replace(":", "_").replace(".", "_")
    log_filename = f"log-{task_id}.json"
    log_path = os.path.join(LOG_DIR, log_filename)
    subfolder = timestamp[:10]

    plan = input_data.get("executionPlanned") or input_data.get(
        "plan") or input_data.get("task") or input_data
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
            "confirmationNeeded": True,
            "taskId": task_id
        }

        try:
            print(f"🧪 Writing confirmable log to path: {log_path}")
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": timestamp,
                    "taskId": task_id,
                    "log_filename": log_filename,
                    "input": input_data,
                    "execution": plan,
                    "result": result,
                    "memory": memory
                }, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            print(f"✅ Confirmable task log written locally: {log_filename}")
        except Exception as e:
            print(f"❌ Failed to write confirmable task log: {e}")

        #upload_log_to_drive(log_path, subfolder)
        record_last_result(memory, plan, result)
        save_memory_context(memory)

        print("🧪 Finished returning confirmable response")
        return {
            "result": result,
            "executionPlanned": plan,
            "fallbackUsed": fallback_used,
            "memory": memory,
            "taskId": task_id,  # Consistently use the generated task_id
            "timestamp": timestamp,
            "roadmap": {
                "currentPhase": "Phase 4.6",
                "nextPhase": "Phase 4.7 – External Tools + Test Suites",
                "subgoal":
                "Enable self-awareness and task parallelism tracking."
            },
            "overallGoal": get_current_goal(memory),
            "phase": "Phase 4.6 – Self Awareness and Parallelism",
            "log_filename": log_filename
        }

    result = execute_task(plan)
    record_last_result(memory, plan, result, fallback_used)

    if not result.get("success"):
        task_summary = f"[{plan.get('intent') or plan.get('action')}] {plan.get('filename', '')} - {plan.get('notes', '')}".strip()
        add_failure_pattern(memory, {"task": task_summary, "result": result})

        # Auto-generate follow-up task
        follow_up_task = {
            "intent": "fix_failure",
            "original_task": task_summary,
            "error": result.get("error", "Unknown error"),
            "requires_confirmation": True,
            "notes":
            f"Auto-generated fix attempt for failed task: {task_summary}"
        }
        add_next_step(memory, follow_up_task)

    save_memory_context(memory)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(
                {
                    "timestamp": timestamp,   
                    "taskId": task_id,
                    "log_filename": log_filename,
                    "input": input_data,
                    "execution": plan,
                    "result": result,
                    "memory": memory
                },
                f,
                indent=2)
            print(f"✅ Log file written: {log_filename}")
    except Exception as e:
        print(f"❌ Failed to write log file: {e}")
        print("📁 Verifying file presence at:", log_path)
        print("📂 Logs directory contains:", os.listdir(LOG_DIR))

   # upload_log_to_drive(log_path, subfolder)

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
            json.dump(
                {
                    "timestamp": timestamp,
                    "taskId": task_id,
                    "log_filename": log_filename,
                    "input": task,
                    "execution": task,
                    "result": result,
                    "memory": memory
                },
                f,
                indent=2)
        print(f"✅ Task log saved: {log_filename}")
    except Exception as e:
        print(f"❌ Error saving task log: {e}")

   # upload_log_to_drive(log_path, subfolder)

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

    try:
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
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"error": f"Error running tests: {e}"}


def finalize_task_execution(status, task_info=None):
    memory = load_memory()
    intent = None

    if task_info:
        intent = (task_info.get("execution", {}).get("action")
                  or task_info.get("execution", {}).get("intent")
                  or task_info.get("input", {}).get("intent"))

    if status == "confirmed":
        track_confirmed(memory)
        if intent:
            stats = memory.setdefault("intent_stats",
                                      {}).setdefault(intent, {})
            stats["success"] = stats.get("success", 0) + 1

    elif status == "rejected":
        track_rejected(memory)
        if intent:
            stats = memory.setdefault("intent_stats",
                                      {}).setdefault(intent, {})
            stats["failure"] = stats.get("failure", 0) + 1
            add_failure_pattern(
                memory, {
                    "intent": intent,
                    "task": f"{intent} – Rejected by user",
                    "timestamp": datetime.now(UTC).isoformat()
                })

    save_memory_context(memory)
    return {"success": True, "status": status, "intent": intent}


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

    return {
        "success": True,
        "message": f"✅ Modified {filename}, backup saved as {backup_name}"
    }

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        try:
            if arg.endswith(".json") and os.path.exists(arg):
                with open(arg, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                print(f"▶️ Loaded task from file: {arg}")
            else:
                # Assume it's raw JSON string input
                task_data = json.loads(arg)
                print(f"▶️ Loaded task from CLI input: {arg[:50]}...")
            run_agent(task_data)
        except Exception as e:
            print(f"❌ Failed to load or run task: {e}")
    else:
        print("⚠️ No task provided. Pass JSON string or filename.")