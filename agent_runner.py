# agent_runner.py

import os
import re
import json
from datetime import datetime
from drive_uploader import upload_log_to_drive
from sandbox_runner import run_in_sandbox
from task_executor import execute_task
from context_manager import (
    load_memory_context,
    save_memory_context,
    record_intent_stats,
    append_self_note,
    increment_confirmed,
    increment_rejected,
    track_failure_pattern
)

def run_agent(input_data):
    memory = load_memory_context()

    if input_data.get("intent") == "run_tests_from_file":
        return run_test_suite(input_data.get("filename", "test_suite.json"))

    task = input_data.get("task", "No task provided")
    code = input_data.get("code", "")
    intent = input_data.get("intent", "").strip().lower()
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    today_str = timestamp.split("T")[0]

    keyword = extract_keyword(task)
    safe_time = timestamp.replace(":", "_")
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = os.path.join(logs_dir, f"log-{keyword}-{safe_time}.json")

    response = {
        "timestamp": timestamp,
        "taskReceived": task,
        "codeBlock": bool(code),
        "phase": "Phase 3.3 – Planning Memory",
        "overallGoal": "Create a real-world agent that builds itself via GPT+user instructions.",
        "roadmap": {
            "currentPhase": "Phase 3.3",
            "nextPhase": "Phase 4 – Self-Modifying Agent",
            "subgoal": "Track recent task behavior, decisions, and outcomes."
        },
        "confirmationNeeded": True,
        "executionPlanned": None,
        "executionResult": None,
        "fallbackUsed": False,
        "logs": [],
        "memory": memory
    }

    if code:
        sandbox_result = run_in_sandbox(code)
        response["logs"].append({"sandboxTest": sandbox_result})
        if sandbox_result["success"] and not sandbox_result.get("error"):
            response["confirmationNeeded"] = False
            response["simulated"] = "✅ Code passed sandbox test. Ready to execute."
        else:
            response["simulated"] = f"❌ Sandbox rejected the code: {sandbox_result.get('error')}"
            return response

    action_plan, fallback_used = dispatch_intent(intent, task, input_data)
    response["executionPlanned"] = action_plan
    response["fallbackUsed"] = fallback_used
    response["logs"].append({"intentDispatch": action_plan or "⚠️ No valid plan"})

    if not response["confirmationNeeded"] and action_plan:
        try:
            result = execute_task(action_plan)
            response["executionResult"] = result
            response["logs"].append({"execution": result})

            finalize_task_execution(response)

        except Exception as e:
            error = {"success": False, "error": f"Execution failed: {str(e)}"}
            response["executionResult"] = error
            response["logs"].append({"executionError": error})
            finalize_task_execution(response)

    try:
        with open(log_filename, "w") as f:
            json.dump(response, f, indent=2)
        print(f"📁 Log saved: {log_filename}")
    except Exception as e:
        print(f"❌ Failed to save log: {e}")

    try:
        file_id, file_link = upload_log_to_drive(log_filename, today_str)
        response["driveFileId"] = file_id
        response["driveFileLink"] = file_link
        print(f"✅ Uploaded to Google Drive: {file_link}")
    except Exception as e:
        response["driveUploadError"] = str(e)
        print(f"❌ Drive upload failed: {e}")

    return response

def finalize_task_execution(log_data):
    if not log_data:
        return

    memory = load_memory_context()
    task = log_data.get("taskReceived")
    result = log_data.get("executionResult") or {}
    success = result.get("success", False)
    intent = (log_data.get("executionPlanned") or {}).get("action", "unknown")

    # Inline memory update logic to avoid stale context
    memory["last_updated"] = datetime.utcnow().isoformat()
    memory["last_result"] = {
        "task": task,
        "intent": intent,
        "status": "success" if success else "fail",
        "timestamp": memory["last_updated"],
        "result": result
    }

    memory["recent_tasks"].append(memory["last_result"])
    if len(memory["recent_tasks"]) > 10:
        memory["recent_tasks"] = memory["recent_tasks"][-10:]

    record_intent_stats(memory, intent, success)

    if success:
        increment_confirmed(memory)
    else:
        track_failure_pattern(memory, task, str(result))
        append_self_note(memory, f"❌ Task failed: {task}")

    save_memory_context(memory)

def extract_keyword(task):
    if "about" in task.lower():
        return task.lower().split("about")[-1].strip().split()[0]
    return task.strip().split()[0].lower() if task else "task"

def dispatch_intent(intent, task, data):
    fallback_used = False

    if intent:
        match intent:
            case "create_file":
                return {
                    "action": "create_file",
                    "filename": data.get("filename"),
                    "content": data.get("content", ""),
                    "notes": "Create file with specified content."
                }, fallback_used
            case "append_to_file":
                return {
                    "action": "append_to_file",
                    "filename": data.get("filename"),
                    "content": data.get("content", ""),
                    "notes": "Append content to an existing file."
                }, fallback_used
            case "edit_file":
                return {
                    "action": "edit_file",
                    "filename": data.get("filename"),
                    "instructions": data.get("instructions", ""),
                    "notes": "Edit the file using natural language instructions."
                }, fallback_used
            case "delete_file":
                return {
                    "action": "delete_file",
                    "filename": data.get("filename"),
                    "notes": "Smartly inferred: delete_file"
                }, fallback_used
            case "rename_file":
                return {
                    "action": "rename_file",
                    "old_name": data.get("old_name"),
                    "new_name": data.get("new_name"),
                    "notes": "Rename file."
                }, fallback_used
            case "deploy":
                return {
                    "action": "deploy",
                    "notes": "Deploy via Git and Render."
                }, fallback_used

    fallback_used = True
    task_lower = task.lower()

    match_create = re.search(r"create (?:a )?file named ['\"]?([\w\-.]+)['\"]?", task_lower)
    match_append = re.search(r"append .* to ['\"]?([\w\-.]+)['\"]?", task_lower)
    match_edit = re.search(r"replace .* in ['\"]?([\w\-.]+)['\"]?", task_lower)
    match_delete = re.search(r"(?:delete|remove) (?:the )?file ['\"]?([\w\-.]+)['\"]?", task_lower)

    if match_create:
        filename = match_create.group(1)
        return {
            "action": "create_file",
            "filename": filename,
            "content": data.get("content", "Hello World"),
            "notes": "Smartly inferred: create_file"
        }, fallback_used

    if match_append:
        filename = match_append.group(1)
        return {
            "action": "append_to_file",
            "filename": filename,
            "content": data.get("content", "Additional content."),
            "notes": "Smartly inferred: append_to_file"
        }, fallback_used

    if match_edit:
        filename = match_edit.group(1)
        return {
            "action": "edit_file",
            "filename": filename,
            "instructions": data.get("instructions", task),
            "notes": "Smartly inferred: edit_file"
        }, fallback_used

    if match_delete:
        filename = match_delete.group(1)
        return {
            "action": "delete_file",
            "filename": filename,
            "notes": "Smartly inferred: delete_file"
        }, fallback_used

    if "summarize" in task_lower or "list" in task_lower:
        return {
            "action": "review",
            "notes": "Task could not be mapped. Review needed before execution."
        }, fallback_used

    return {
        "action": "review",
        "notes": "Task could not be mapped. Review needed before execution."
    }, fallback_used

def run_test_suite(filename):
    with open(filename, "r") as f:
        test_suite = json.load(f)

    results = []
    passed = 0
    failed = 0

    for i, test in enumerate(test_suite.get("tests", []), 1):
        task = test.get("task", "")
        intent = test.get("intent", "")
        expected = test.get("expected", {})

        result, _ = dispatch_intent(intent, task, test)
        comparison = all(result.get(k) == v for k, v in expected.items())

        log_data = {
            "taskReceived": task,
            "executionPlanned": result,
            "executionResult": {"success": comparison}
        }

        finalize_task_execution(log_data)

        results.append({
            "test": i,
            "task": task,
            "intent": intent,
            "expected": expected,
            "actual": result,
            "passed": comparison
        })

    timestamp = datetime.utcnow().isoformat()
    safe_time = timestamp.replace(":", "_").split(".")[0]
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = os.path.join(logs_dir, f"log-test-suite-{safe_time}.json")

    wrapped = {
        "timestamp": timestamp,
        "confirmationNeeded": False,
        "executionPlanned": {
            "action": "run_tests_from_file",
            "notes": f"Ran test suite from {filename}"
        },
        "executionResult": {
            "success": failed == 0,
            "summary": f"{passed} passed, {failed} failed",
            "results": results
        }
    }

    with open(log_filename, "w") as f:
        json.dump(wrapped, f, indent=2)

    upload_log_to_drive(log_filename, timestamp.split("T")[0])

    return {
        "filename": os.path.basename(log_filename),
        "content": wrapped
    }
