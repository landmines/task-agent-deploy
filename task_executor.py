# task_executor.py
import os

# Adjust this to your actual Replit project path if needed
REPLIT_PROJECT_ROOT = "/home/runner/task-agent-deploy"  # <--- Update this if your project folder is named differently

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

    if not filename or "/" in filename or "\\" in filename:
        return {
            "success": False,
            "error": "Invalid filename."
        }

    try:
        full_path = os.path.join(REPLIT_PROJECT_ROOT, filename)
        with open(full_path, "w") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"✅ File '{full_path}' created successfully."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def append_to_file(plan):
    filename = plan.get("filename")
    content = plan.get("content", "")

    if not filename or "/" in filename or "\\" in filename:
        return {
            "success": False,
            "error": "Invalid filename."
        }

    full_path = os.path.join(REPLIT_PROJECT_ROOT, filename)

    if not os.path.exists(full_path):
        return {
            "success": False,
            "error": f"File '{full_path}' does not exist. Cannot append."
        }

    try:
        with open(full_path, "a") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"✅ Content appended to '{full_path}'."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
