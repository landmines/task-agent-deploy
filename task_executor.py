import os
import re
from datetime import datetime

# ✅ Safe and visible path for both Replit and Render deployments
PROJECT_ROOT = "/opt/render/project/src" if os.getenv("RENDER") else os.getcwd()

def execute_task(plan):
    action = plan.get("action") or plan.get("intent")

    if action == "create_file":
        return create_file(plan)
    elif action == "append_to_file":
        return append_to_file(plan)
    elif action == "edit_file":
        return edit_file(plan)
    elif action == "delete_file":
        return delete_file(plan)
    else:
        return {
            "success": False,
            "error": f"Unsupported action: {action}"
        }

def create_file(plan):
    filename = plan.get("filename")
    content = plan.get("content", "")

    if not filename or "/" in filename or "\\" in filename:
        return {"success": False, "error": "Invalid filename."}

    full_path = os.path.join(PROJECT_ROOT, filename)
    try:
        with open(full_path, "w") as f:
            f.write(content)
        return {"success": True, "message": f"✅ File created at: {full_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def append_to_file(plan):
    filename = plan.get("filename")
    content = plan.get("content", "")

    if not filename or "/" in filename or "\\" in filename:
        return {"success": False, "error": "Invalid filename."}

    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File '{full_path}' does not exist. Cannot append."}

    try:
        with open(full_path, "a") as f:
            f.write(content)
        return {"success": True, "message": f"✅ Appended to file: {full_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def edit_file(plan):
    filename = plan.get("filename")
    instructions = plan.get("instructions", "")

    if not filename or "/" in filename or "\\" in filename:
        return {"success": False, "error": "Invalid filename."}

    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File '{full_path}' does not exist. Cannot edit."}

    try:
        with open(full_path, "r") as f:
            original = f.read()

        new_content = original
        change_made = False

        # 1. Replace all 'X' with 'Y'
        match = re.match(r"replace all '(.*)' with '(.*)'", instructions, re.IGNORECASE)
        if match:
            target, repl = match.groups()
            if target in original:
                new_content = original.replace(target, repl)
                change_made = True
            else:
                return {"success": False, "error": f"❌ Text '{target}' not found for replacement."}

        # 2. Delete line containing 'X'
        match = re.match(r"delete line containing '(.*)'", instructions, re.IGNORECASE)
        if match:
            keyword = match.group(1)
            lines = new_content.splitlines()
            filtered = [line for line in lines if keyword not in line]
            if len(lines) != len(filtered):
                new_content = "\n".join(filtered) + "\n"
                change_made = True
            else:
                return {"success": False, "error": f"❌ No lines found containing '{keyword}'"}

        # 3. Replace line 'X' with 'Y'
        match = re.match(r"replace line '(.*)' with '(.*)'", instructions, re.IGNORECASE)
        if match:
            old_line, new_line = match.groups()
            lines = new_content.splitlines()
            updated = []
            replaced = False
            for line in lines:
                if line.strip() == old_line.strip():
                    updated.append(new_line)
                    replaced = True
                else:
                    updated.append(line)
            if replaced:
                new_content = "\n".join(updated) + "\n"
                change_made = True
            else:
                return {"success": False, "error": f"❌ Exact line '{old_line}' not found."}

        if not change_made:
            return {"success": False, "error": "❌ Could not understand or apply edit instructions."}

        # Create backup
        timestamp = datetime.utcnow().isoformat().replace(":", "-").split(".")[0]
        backup_name = f"{filename}_BACKUP_{timestamp}"
        backup_path = os.path.join(PROJECT_ROOT, backup_name)
        with open(backup_path, "w") as f:
            f.write(original)

        # Apply new content
        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "success": True,
            "message": f"✅ File '{filename}' edited with backup created: {backup_name}",
            "backup": backup_name,
            "original_file": filename,
            "instructions": instructions,
            "timestamp": timestamp
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_file(plan):
    filename = plan.get("filename")
    if not filename or "/" in filename or "\\" in filename:
        return {"success": False, "error": "Invalid filename."}

    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File '{full_path}' not found. Nothing to delete."}

    try:
        os.remove(full_path)
        return {"success": True, "message": f"🗑️ File deleted: {full_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}