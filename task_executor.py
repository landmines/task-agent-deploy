# task_executor.py
import os
import re

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

        new_content = content
        change_made = False

        # 1. Match: replace all 'X' with 'Y'
        match_replace = re.match(r"replace all '(.*)' with '(.*)'", instructions, re.IGNORECASE)
        if match_replace:
            target, repl = match_replace.groups()
            if target in new_content:
                new_content = new_content.replace(target, repl)
                change_made = True
            else:
                return {
                    "success": False,
                    "error": f"❌ Text '{target}' not found for replacement."
                }

        # 2. Match: delete line containing 'X'
        match_delete = re.match(r"delete line containing '(.*)'", instructions, re.IGNORECASE)
        if match_delete:
            keyword = match_delete.group(1)
            lines = new_content.splitlines()
            filtered = [line for line in lines if keyword not in line]
            if len(lines) != len(filtered):
                new_content = "\n".join(filtered) + "\n"
                change_made = True
            else:
                return {
                    "success": False,
                    "error": f"❌ No lines found containing '{keyword}'"
                }

        # 3. Match: replace line 'X' with 'Y'
        match_line_replace = re.match(r"replace line '(.*)' with '(.*)'", instructions, re.IGNORECASE)
        if match_line_replace:
            old_line, new_line = match_line_replace.groups()
            lines = new_content.splitlines()
            replaced = False
            updated_lines = []
            for line in lines:
                if line.strip() == old_line.strip():
                    updated_lines.append(new_line)
                    replaced = True
                else:
                    updated_lines.append(line)
            if replaced:
                new_content = "\n".join(updated_lines) + "\n"
                change_made = True
            else:
                return {
                    "success": False,
                    "error": f"❌ Exact line '{old_line}' not found for replacement."
                }

        if not change_made:
            return {
                "success": False,
                "error": "❌ Could not understand or apply edit instructions."
            }

        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "success": True,
            "message": f"✅ File '{filename}' edited using instructions: {instructions}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
