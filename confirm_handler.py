# confirm_handler.py
import os
import json
import glob
from datetime import datetime, UTC
from task_executor import execute_task
from drive_uploader import upload_log_to_drive

def confirm_task(task_id):
    logs_dir = "logs"

    # Normalize timestamp (remove microseconds, special characters)
    base_ts = task_id.split(".")[0].strip()  # 2025-04-08T16:14:32
    base_ts_clean = base_ts.replace(":", "_").replace("/", "_").replace(".", "_")

    # Pattern: log-*timestamp*.json
    pattern = os.path.join(logs_dir, f"log-*{base_ts_clean}*.json")
    matching_files = sorted(glob.glob(pattern), reverse=True)

    if not matching_files:
        return {
            "success": False,
            "error": "❌ Log not found.",
            "details": f"Tried pattern: {pattern}",
            "hint": "Make sure timestamp matches filename format exactly."
        }

    log_path = matching_files[0]

    try:
        with open(log_path, "r") as f:
            log_data = json.load(f)
    except Exception as e:
        return {"success": False, "error": f"❌ Failed to read log: {str(e)}"}

    if not log_data.get("executionPlanned"):
        return {"success": False, "error": "⚠️ No execution plan found in log."}

    # Execute the planned action
    result = execute_task(log_data["executionPlanned"])
    log_data["confirmed"] = True
    log_data["executionResult"] = result

    try:
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        return {"success": False, "error": f"❌ Failed to save updated log: {str(e)}"}

    # Optional: Upload to Drive
    try:
        today_str = datetime.now(UTC).isoformat().split("T")[0]
        file_id, file_link = upload_log_to_drive(log_path, today_str)
        log_data["driveFileLink"] = file_link
        log_data["driveFileId"] = file_id
    except Exception as e:
        log_data["driveUploadError"] = str(e)

    return {
        "success": True,
        "message": f"✅ Task confirmed and executed from: {os.path.basename(log_path)}",
        "result": result
    }
