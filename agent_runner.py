import os
import json
from datetime import datetime
from drive_uploader import upload_log_to_drive
from sandbox_runner import run_in_sandbox
from task_executor import execute_task

def run_agent(input_data):
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

    # 🧠 Core response log structure (for memory and planning)
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

    # 🔍 Optional sandbox test (for code execution)
    if code:
        sandbox_result = run_in_sandbox(code)
        response["logs"].append({"sandboxTest": sandbox_result})
        if sandbox_result["success"] and not sandbox_result.get("error"):
            response["confirmationNeeded"] = False
            response["simulated"] = "✅ Code passed sandbox test. Ready to execute."
        else:
            response["simulated"] = f"❌ Sandbox rejected the code: {sandbox_result.get('error')}"
            return response

    # 📋 Dispatch intent (explicit or inferred)
    try:
        action_plan = dispatch_intent(intent, task, input_data)
        response["executionPlanned"] = action_plan
        response["logs"].append({"intentDispatch": action_plan})
        if action_plan.get("notes", "").startswith("Smartly inferred"):
            response["fallbackUsed"] = True
    except Exception as e:
        response["logs"].append({"intentDispatch": f"❌ Dispatch error: {str(e)}"})
        response["executionPlanned"] = None

    # 🚀 Auto-execute only if confirmation not required
    if not response["confirmationNeeded"] and response["executionPlanned"]:
        try:
            result = execute_task(response["executionPlanned"])
            response["executionResult"] = result
            response["logs"].append({"execution": result})
        except Exception as e:
            error = {"success": False, "error": f"Execution failed: {str(e)}"}
            response["executionResult"] = error
            response["logs"].append({"executionError": error})

    # 💾 Save locally
    try:
        with open(log_filename, "w") as f:
            json.dump(response, f, indent=2)
        print(f"📁 Log saved: {log_filename}")
    except Exception as e:
        print(f"❌ Failed to save log: {e}")

    # ☁️ Upload to Drive
    try:
        file_id, file_link = upload_log_to_drive(log_filename, today_str)
        response["driveFileId"] = file_id
        response["driveFileLink"] = file_link
        print(f"✅ Uploaded to Google Drive: {file_link}")
    except Exception as e:
        response["driveUploadError"] = str(e)
        print(f"❌ Drive upload failed: {e}")

    return response

# 🔎 Extracts a keyword to use in the log filename
def extract_keyword(task):
    if "about" in task.lower():
        return task.lower().split("about")[-1].strip().split()[0]
    return task.strip().split()[0].lower() if task else "task"

# 🧠 Smart or explicit dispatch logic
def dispatch_intent(intent, raw_task, data):
    if intent:
        match intent:
            case "create_file":
                return {
                    "action": "create_file",
                    "filename": data.get("filename"),
                    "content": data.get("content", ""),
                    "notes": "Create file with specified content."
                }
            case "append_to_file":
                return {
                    "action": "append_to_file",
                    "filename": data.get("filename"),
                    "content": data.get("content", ""),
                    "notes": "Append content to an existing file."
                }
            case "edit_file":
                return {
                    "action": "edit_file",
                    "filename": data.get("filename"),
                    "instructions": data.get("instructions", ""),
                    "notes": "Edit the file using natural language instructions."
                }
            case "delete_file":
                return {
                    "action": "delete_file",
                    "filename": data.get("filename"),
                    "notes": "Delete file — confirmation required."
                }
            case "rename_file":
                return {
                    "action": "rename_file",
                    "old_name": data.get("old_name"),
                    "new_name": data.get("new_name"),
                    "notes": "Rename file."
                }
            case "run_code_only":
                return {
                    "action": "run_code_only",
                    "notes": "Will execute code in sandbox only."
                }
            case "deploy":
                return {
                    "action": "deploy",
                    "notes": "Deploy via Git and Render."
                }

    # 🧠 Natural language fallback intent detection
    task_text = raw_task.lower()
    if "create" in task_text and "file" in task_text:
        return {
            "action": "create_file",
            "filename": data.get("filename", "newfile.txt"),
            "content": data.get("content", "Hello World"),
            "notes": "Smartly inferred: create_file"
        }
    elif "append" in task_text:
        return {
            "action": "append_to_file",
            "filename": data.get("filename", "log.txt"),
            "content": data.get("content", "Additional content."),
            "notes": "Smartly inferred: append_to_file"
        }
    elif "edit" in task_text or "replace" in task_text or "delete line" in task_text:
        return {
            "action": "edit_file",
            "filename": data.get("filename", "example.txt"),
            "instructions": data.get("instructions", task_text),
            "notes": "Smartly inferred: edit_file"
        }
    else:
        return {
            "action": "review",
            "notes": "Task could not be mapped. Review needed before execution."
        }
