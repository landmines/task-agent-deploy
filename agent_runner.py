import os
import re
import json
from datetime import datetime
from drive_uploader import upload_log_to_drive
from sandbox_runner import run_in_sandbox
from task_executor import execute_task

PROJECT_ROOT = "/opt/render/project/src" if os.getenv("RENDER") else os.getcwd()

def run_agent(input_data):
    intent = input_data.get("intent", "").strip().lower()

    if intent == "run_tests_from_file":
        return run_test_suite(input_data.get("filename", "test_suite.json"))

    task = input_data.get("task", "No task provided")
    code = input_data.get("code", "")
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    today_str = timestamp.split("T")[0]
    keyword = extract_keyword(task)
    safe_time = timestamp.replace(":", "_")
    logs_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = os.path.join(logs_dir, f"log-{keyword}-{safe_time}.json")

    response = {
        "timestamp": timestamp,
        "taskReceived": task,
        "codeBlock": bool(code),
        "phase": "Phase 3.2 – Natural Task Planning",
        "overallGoal": "Create a self-evolving task agent with confirmation and execution control.",
        "roadmap": {
            "currentPhase": "Phase 3.2",
            "nextPhase": "Phase 3.3 – Planning Memory",
            "subgoal": "Interpret general tasks and simulate actions before execution"
        },
        "confirmationNeeded": True,
        "executionPlanned": None,
        "executionResult": None,
        "logs": []
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
    response["fallbackUsed"] = fallback_used

    if action_plan:
        response["executionPlanned"] = action_plan
        response["logs"].append({"intentDispatch": action_plan})
    else:
        response["logs"].append({"intentDispatch": "⚠️ No valid plan could be generated."})

    if not response["confirmationNeeded"] and response["executionPlanned"]:
        try:
            result = execute_task(response["executionPlanned"])
            response["executionResult"] = result
            response["logs"].append({"execution": result})
        except Exception as e:
            error = {"success": False, "error": f"Execution failed: {str(e)}"}
            response["executionResult"] = error
            response["logs"].append({"executionError": error})

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

def run_test_suite(filename):
    suite_path = os.path.join(PROJECT_ROOT, filename)
    try:
        with open(suite_path) as f:
            tests = json.load(f)
    except Exception as e:
        return {"success": False, "error": f"Failed to load test suite: {e}"}

    results = []
    passed = 0
    failed = 0

    for i, test in enumerate(tests, 1):
        task = test.get("task", "")
        intent = test.get("intent", "")
        expected = test.get("expected", {})
        plan, fallback_used = dispatch_intent(intent, task, test)

        success = (
            plan.get("action") == expected.get("action") and
            plan.get("filename") == expected.get("filename")
        )

        result = {
            "test": i,
            "task": task,
            "intent": intent,
            "expected": expected,
            "actual": plan,
            "passed": success
        }

        results.append(result)
        passed += 1 if success else 0
        failed += 0 if success else 1

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "testFile": filename,
        "totalTests": len(tests),
        "passed": passed,
        "failed": failed,
        "results": results
    }

    # Write test results to log
    safe_time = datetime.utcnow().replace(":", "_").split(".")[0]
    logs_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = os.path.join(logs_dir, f"test-results-{safe_time}.json")

    with open(log_filename, "w") as f:
        json.dump(summary, f, indent=2)

    try:
        upload_log_to_drive(log_filename, datetime.utcnow().strftime("%Y-%m-%d"))
    except Exception as e:
        print("Drive upload failed:", str(e))

    return summary

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
                    "notes": "Delete file — confirmation required."
                }, fallback_used
            case "rename_file":
                return {
                    "action": "rename_file",
                    "old_name": data.get("old_name"),
                    "new_name": data.get("new_name"),
                    "notes": "Rename file."
                }, fallback_used
            case "run_code_only":
                return {
                    "action": "run_code_only",
                    "notes": "Will execute code in sandbox only."
                }, fallback_used
            case "deploy":
                return {
                    "action": "deploy",
                    "notes": "Deploy via Git and Render."
                }, fallback_used

    # 🧠 Natural fallback
    fallback_used = True
    task_lower = task.lower()

    match_create = re.search(r"create (?:a )?file named ['\"]?([\w\-.]+)['\"]?", task_lower)
    match_append = re.search(r"append .* to ['\"]?([\w\-.]+)['\"]?", task_lower)
    match_edit = re.search(r"replace .* in ['\"]?([\w\-.]+)['\"]?", task_lower)

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

    if "summarize" in task_lower or "list" in task_lower:
        return {
            "action": "review",
            "notes": "Task could not be mapped. Review needed before execution."
        }, fallback_used

    return {
        "action": "review",
        "notes": "Task could not be mapped. Review needed before execution."
    }, fallback_used
