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
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()  # strip microseconds
    today_str = timestamp.split("T")[0]

    keyword = "task"
    if "about" in task.lower():
        keyword = task.lower().split("about")[-1].strip().split()[0]
    elif task:
        keyword = task.strip().split()[0].lower()

    safe_time = timestamp.replace(":", "_")
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = os.path.join(logs_dir, f"log-{keyword}-{safe_time}.json")

    response = {
        "timestamp": timestamp,
        "intro": "Hi, I'm Task Executor. How can I help you today?",
        "behavior": (
            "You are a helpful assistant that receives tasks in natural language. "
            "You carefully analyze each request to understand what the user wants. "
            "You simulate results, request confirmation, and act responsibly. "
            "You maintain logs, follow user intent, and support deployment."
        ),
        "taskReceived": task,
        "simulated": f"Simulating task: '{task}'...",
        "confirmationNeeded": True,
        "executionPlanned": None
    }

    # Optional: Run sandbox test
    if code:
        sandbox_result = run_in_sandbox(code)
        response["sandboxTest"] = sandbox_result
        if sandbox_result["success"] and not sandbox_result.get("error"):
            response["simulated"] = "✅ Code passed sandbox test. Ready to execute with your approval."
            response["confirmationNeeded"] = False
        else:
            response["simulated"] = f"❌ Sandbox rejected the code: {sandbox_result.get('error')}"
            return response

    # Build action plan
    action_plan = dispatch_intent(intent, input_data)
    if action_plan:
        response["executionPlanned"] = action_plan

    # Execute now if no confirmation needed
    if not response["confirmationNeeded"] and response["executionPlanned"]:
        try:
            result = execute_task(response["executionPlanned"])
            response["executionResult"] = result
        except Exception as e:
            response["executionResult"] = {
                "success": False,
                "error": f"Execution failed: {str(e)}"
            }

    # Save log locally
    try:
        with open(log_filename, "w") as f:
            json.dump(response, f, indent=2)
        print(f"📁 Log saved: {log_filename}")
    except Exception as e:
        print(f"❌ Failed to save log: {e}")

    # Upload to Drive
    try:
        file_id, file_link = upload_log_to_drive(log_filename, today_str)
        response["driveFileId"] = file_id
        response["driveFileLink"] = file_link
        print(f"✅ Uploaded to Google Drive: {file_link}")
    except Exception as e:
        response["driveUploadError"] = str(e)
        print(f"❌ Drive upload failed: {e}")

    return response

# Dispatcher
def dispatch_intent(intent, input_data):
    match intent:
        case "create_file":
            return {
                "action": "create_file",
                "filename": input_data.get("filename"),
                "content": input_data.get("content", ""),
                "notes": "Will create the file with specified content after confirmation."
            }
        case "append_to_file":
            return {
                "action": "append_to_file",
                "filename": input_data.get("filename"),
                "content": input_data.get("content", ""),
                "notes": "Will append content to an existing file, if it exists."
            }
        case "edit_file":
            return {
                "action": "edit_file",
                "filename": input_data.get("filename"),
                "instructions": input_data.get("instructions", ""),
                "notes": "Will attempt to edit based on natural language instructions."
            }
        case "delete_file":
            return {
                "action": "delete_file",
                "filename": input_data.get("filename"),
                "notes": "Destructive action. Requires explicit confirmation before proceeding."
            }
        case "rename_file":
            return {
                "action": "rename_file",
                "old_name": input_data.get("old_name"),
                "new_name": input_data.get("new_name"),
                "notes": "Will rename file if both names are valid."
            }
        case "deploy":
            return {
                "action": "deploy",
                "notes": "Triggering deployment via Git and Render."
            }
        case "run_code_only":
            return {
                "action": "run_code_only",
                "notes": "Will execute the provided code in a sandbox environment."
            }
        case "general_task" | "":
            return {
                "action": "review",
                "notes": "No specific intent found. Will prompt user for clarification or manual guidance."
            }
        case _:
            return {
                "action": "unknown",
                "notes": f"Intent '{intent}' not recognized. Will request user help."
            }
