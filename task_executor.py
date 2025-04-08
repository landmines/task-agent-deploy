# task_executor.py
import os

# ✅ Safe and visible path for both Replit and Render deployments
PROJECT_ROOT = "/opt/render/project/src" if os.getenv("RENDER") else os.getcwd()

def execute_task(plan):
    action = plan.get("action")

    if action == "create_file":
        return create_file(plan)
    elif action == "append_to_file":
        return append_to_file(plan)
    elif action == "edit_file":
        return edit_file(plan)
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

    full_path = os.path.join(PROJECT_ROOT, filename)

    try:
        with open(full_path, "w") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"✅ File created at: {full_path}"
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

    full_path = os.path.join(PROJECT_ROOT, filename)

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
            "message": f"✅ Appended to file: {full_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def edit_file(plan):
    filename = plan.get("filename")
    instructions = plan.get("instructions", "")
    replacement = plan.get("replacement", "")

    if not filename or "/" in filename or "\\" in filename:
        return {
            "success": False,
            "error": "Invalid filename."
        }

    full_path = os.path.join(PROJECT_ROOT, filename)

    if not os.path.exists(full_path):
        return {
            "success": False,
            "error": f"File '{full_path}' does not exist. Cannot edit."
        }

    try:
        with open(full_path, "r") as f:
            content = f.read()

        if instructions in content:
            new_content = content.replace(instructions, replacement)
        else:
            return {
                "success": False,
                "error": "❌ Instruction text not found in file."
            }

        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "success": True,
            "message": f"✅ Edited '{full_path}' using instructions."
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
