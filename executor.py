# executor.py
import os
from datetime import datetime, UTC

def execute_action(action_plan):
    result = {
        "action": action_plan.get("action"),
        "status": "not_executed",
        "message": "",
        "timestamp": datetime.now(UTC).isoformat()
    }

    try:
        match action_plan.get("action"):
            case "create_file":
                filename = action_plan.get("filename")
                content = action_plan.get("content", "")
                if not filename:
                    raise ValueError("Missing filename")

                # Prevent path traversal
                if ".." in filename or filename.startswith("/"):
                    raise ValueError("Invalid filename path")

                with open(filename, "w") as f:
                    f.write(content)

                result["status"] = "success"
                result["message"] = f"File '{filename}' created."

            case _:
                result["status"] = "skipped"
                result["message"] = f"Action '{action_plan.get('action')}' not handled yet."

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result
