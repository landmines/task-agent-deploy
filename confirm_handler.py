# confirm_handler.py
import os
import json
from task_executor import execute_task
from drive_uploader import upload_log_to_drive
from datetime import datetime

# confirm_handler.py

def needs_confirmation(action_type):
    # You can customize which actions require confirmation
    return action_type in {"create_file", "edit_file", "delete_file", "rename_file", "deploy"}


def confirm_task(task_id):
    log_path = os.path.join("logs", f"{task_id}.json")
    if not os.path.exists(log_path):
        return {"success": False, "error": "Log not found."}

    with open(log_path, "r") as f:
        log_data = json.load(f)

    if not log_data.get("executionPlanned"):
        return {"success": False, "error": "No execution plan found in log."}

    result = execute_task(log_data["executionPlanned"])
    log_data["confirmed"] = True
    log_data["executionResult"] = result

    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)

    try:
        today_str = datetime.utcnow().isoformat().split("T")[0]
        file_id, file_link = upload_log_to_drive(log_path, today_str)
        log_data["driveFileLink"] = file_link
        log_data["driveFileId"] = file_id
    except Exception as e:
        log_data["driveUploadError"] = str(e)

    return {"success": True, "message": "Task confirmed and executed.", "result": result}
