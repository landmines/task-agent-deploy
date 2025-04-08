# confirm_handler.py
import os
import json
import glob
from datetime import datetime
from task_executor import execute_task
from drive_uploader import upload_log_to_drive


def confirm_task(task_id):
    logs_dir = "logs"

    # Step 1: Remove microseconds
    base_ts = task_id.split(".")[0]  # e.g., 2025-04-08T15:48:14
    base_ts_clean = base_ts.replace(":", "_").replace(".", "_").strip()

    # Step 2: Create pattern that matches log filename format
    pattern = os.path.join(logs_dir, f"log-*{base_ts_clean}*.json")
    matching_files = sorted(glob.glob(pattern), reverse=True)

    if not matching_files:
        return {
            "success": False,
            "error": f"No log file matched for pattern: {pattern}",
            "hint": "Ensure timestamp stops at seconds (not microseconds)"
        }

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
        "message": f"Task confirmed and executed from {os.path.basename(log_path)}",
        "result": result
    }