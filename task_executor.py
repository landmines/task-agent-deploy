# task_executor.py
import os

def execute_task(plan):
    action = plan.get("action")

    if action == "create_file":
        return create_file(plan)
    elif action == "append_to_file":
        return append_to_file(plan)
    else:
        return {
            "success": False,
            "error": f"Unsupported action: {action}"
        }

def create_file(plan):
    filename = plan.get("filename")
    content = plan.get("content", "")
    try:
        with open(filename, "w") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"✅ File '{filename}' created successfully."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def append_to_file(plan):
    filename = plan.get("filename")
    content = plan.get("content", "")

    if not os.path.exists(filename):
        return {
            "success": False,
            "error": f"File '{filename}' does not exist. Cannot append."
        }

    try:
        with open(filename, "a") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"✅ Content appended to '{filename}'."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
