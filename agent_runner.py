# agent_runner.py
import os
import json
from datetime import datetime
from drive_uploader import upload_log_to_drive
from sandbox_runner import run_in_sandbox

def run_agent(input_data):
    task = input_data.get("task", "No task provided")
    code = input_data.get("code", "")
    timestamp = datetime.utcnow().isoformat()
    today_str = timestamp.split("T")[0]

    keyword = "task"
    if "about" in task.lower():
        keyword = task.lower().split("about")[-1].strip().split()[0]
    elif task:
        keyword = task.strip().split()[0].lower()

    safe_time = timestamp.replace(":", "_").split(".")[0]
    logs_dir = os.path.join(os.getcwd(), "logs")
    log_filename = os.path.join(logs_dir, f"log-{keyword}-{safe_time}.json")

    response = {
        "timestamp": timestamp,
        "intro": "Hi, I'm Task Executor. How can I help you today?",
        "behavior": (
            "You are a helpful assistant that receives tasks in natural language. "
            "You carefully analyze each request to understand what the user wants. "
            "For each task, you first simulate what would happen, then explain the plan "
            "to the user and ask for confirmation before executing it. "
            "You maintain detailed logs of all actions. "
            "You can modify your own workflows and help deploy chatbot applications as requested. "
            "You always take direction only from your user and explain tasks in non-technical language. "
            "You maintain context about your purpose, goals, and progress status to ensure continuity between sessions."
        ),
        "taskReceived": task,
        "simulated": f"Simulating task: '{task}'...",
        "confirmationNeeded": True
    }

    if code:
        sandbox_result = run_in_sandbox(code)
        response["sandboxTest"] = sandbox_result

        if sandbox_result["success"] and not sandbox_result.get("error"):
            response["simulated"] = "✅ Code passed sandbox test. Ready to execute with your approval."
            response["confirmationNeeded"] = False
        else:
            response["simulated"] = f"❌ Sandbox rejected the code: {sandbox_result.get('error')}"
            response["confirmationNeeded"] = True

    os.makedirs(logs_dir, exist_ok=True)
    try:
        with open(log_filename, "w") as f:
            json.dump(response, f, indent=2)
        print(f"📁 Log saved: {log_filename}")
    except Exception as e:
        print(f"❌ Failed to save log: {e}")

    try:
        file_id, file_link = upload_log_to_drive(log_filename, today_str)
        print(f"✅ Uploaded to Google Drive: {file_link}")
        response["driveFileId"] = file_id
        response["driveFileLink"] = file_link
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        response["driveUploadError"] = str(e)

    return response
