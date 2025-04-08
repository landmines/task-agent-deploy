# confirm_handler.py
import os
import json
import glob
from datetime import datetime
from task_executor import execute_task
from drive_uploader import upload_log_to_drive


def needs_confirmation(action_type):
    return action_type in {"create_file", "edit_file", "delete_file", "rename_file", "deploy"}


def confirm_task(task_id):
    logs_dir = "logs"
    pattern = os.path.join(logs_dir, f"log-*{task_id}*.json")
    matching_files = sorted(glob.glob(pattern), reverse=True)

    if not matching_files:
        return {"success": False, "error": "Log not found."}

    log_path = matching_files[0]

    try:
        with open(log_path, "r") as f:
            log_data = json.load(f)
    except Exception as e:
        return {"success": False, "error": f"Failed to read log file: {str(e)}"}

    if not log_data.get("executionPlanned"):
        return {"success": False, "error": "No execution plan found in log."}

    result = execute_task(log_data["executionPlanned"])
    log_data["confirmed"] = True
    log_data["executionResult"] = result

    try:
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        return {"success": False, "error": f"Failed to write log: {str(e)}"}

    try:
        today_str = datetime.utcnow().isoformat().split("T")[0]
        file_id, file_link = upload_log_to_drive(log_path, today_str)
        log_data["driveFileLink"] = file_link
        log_data["driveFileId"] = file_id
    except Exception as e:
        log_data["driveUploadError"] = str(e)

    return {
        "success": True,
        "message": f"Task from {os.path.basename(log_path)} confirmed and executed.",
        "result": result
    }
