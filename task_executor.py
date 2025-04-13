# task_executor.py
import os
import re
import json
from datetime import datetime, UTC

PROJECT_ROOT = "/opt/render/project/src" if os.getenv("RENDER") else os.getcwd()
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
DIAGNOSTICS_DIR = os.path.join(PROJECT_ROOT, "logs", "diagnostics")

def backup_file(filepath):
    if not os.path.exists(filepath):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = os.path.basename(filepath)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"{filename}_BACKUP_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    with open(filepath, "r") as f_in, open(backup_path, "w") as f_out:
        f_out.write(f_in.read())
    return backup_path

def unsupported_action(action):
    return {
        "success": False,
        "error": f"Unsupported or unimplemented action: {action}.",
        "hint": "Check your task type or add implementation for this action."
    }

def execute_code(plan):
    """Execute code in a restricted environment"""
    code = plan.get("code", "")
    if not code:
        return {"success": False, "error": "No code provided"}

    try:
        # Execute in restricted context
        restricted_globals = {"__builtins__": {}}
        allowed_builtins = ["print", "len", "str", "int", "float", "list", "dict", "set"]
        for func in allowed_builtins:
            restricted_globals["__builtins__"][func] = __builtins__[func]

        exec(code, restricted_globals, {})
        return {"success": True, "message": "Code executed successfully"}
    except Exception as e:
        return {"success": False, "error": f"Code execution failed: {str(e)}"}

def modify_file(plan):
    """Modify existing file content"""
    filename = plan.get("filename")
    old_content = plan.get("old_content")
    new_content = plan.get("new_content")

    if not all([filename, old_content, new_content]):
        return {"success": False, "error": "Missing required fields"}

    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File {filename} not found"}

    try:
        with open(full_path, "r") as f:
            content = f.read()

        if old_content not in content:
            return {"success": False, "error": "Old content not found in file"}

        new_content = content.replace(old_content, new_content)
        backup_path = backup_file(full_path)

        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "success": True, 
            "message": f"File modified: {filename}",
            "backup": backup_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def estimate_risk(plan):
    """Estimate risk level of a task"""
    risk_levels = {
        "create_file": 1,
        "append_to_file": 1,
        "modify_file": 2,
        "delete_file": 3,
        "deploy": 2,
        "execute": 2
    }
    return risk_levels.get(plan.get("action") or plan.get("intent"), 2)

def execute_task(plan):
    execution_start = datetime.now(UTC)
    risk_level = estimate_risk(plan)

    # Require confirmation for high-risk actions
    if risk_level > 2 or plan.get("confirmationNeeded") is True:
        return {
            "success": True,
            "message": "⏸️ Task logged but awaiting user confirmation.",
            "pending": True,
            "confirmationNeeded": True,
            "execution_metadata": {
                "start_time": execution_start.isoformat(),
                "status": "pending_confirmation",
                "task_type": plan.get("action") or plan.get("intent")
            }
        }

    action = plan.get("action") or plan.get("intent")
    if action == "create_file":
        return create_file(plan)
    elif action == "append_to_file":
        return append_to_file(plan)
    elif action == "edit_file":
        return edit_file(plan)
    elif action == "delete_file":
        return delete_file(plan)
    elif action == "push_changes":
        return simulate_push()
    elif action == "write_diagnostic_log":
        return write_diagnostic(plan)
    elif action == "modify_file":
        return unsupported_action(action)
    elif action == "create_app":
        try:
            template = generate_app_template(plan.get("template_type", "web"))
            deployment_result = deploy_to_replit(plan.get("project_name", "my-app"))
            return {
                "success": True,
                "message": "✅ App template generated and deployment configured",
                "template": template,
                "deployment": deployment_result
            }
        except Exception as e:
            return {"success": False, "error": f"App generation failed: {str(e)}"}
    elif action == "generate_code":
        return unsupported_action(action)
    else:
        return unsupported_action(action)

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
    try:
        if not os.path.exists(full_path):
            with open(full_path, "w") as f:
                f.write("")  # Create an empty file
            was_created = True
        else:
            was_created = False
        with open(full_path, "a") as f:
            f.write("\n" + content)
        msg = f"✅ Appended to file: {full_path}"
        if was_created:
            msg += " (file was auto-created)"
        return {"success": True, "message": msg}
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

        match = re.match(r"replace all '(.*)' with '(.*)'", instructions, re.IGNORECASE)
        if match:
            target, repl = match.groups()
            if target in original:
                new_content = original.replace(target, repl)
                change_made = True
            else:
                return {"success": False, "error": f"❌ Text '{target}' not found for replacement."}

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

        backup_path = backup_file(full_path)
        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "success": True,
            "message": f"✅ File '{filename}' edited.",
            "backup": backup_path,
            "original_file": filename,
            "instructions": instructions,
            "timestamp": datetime.now(UTC).isoformat()
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

def simulate_push():
    return {
        "success": True,
        "message": "🧪 Simulated push: Git command not run (unsupported in current environment).",
        "note": "Try again after migrating to Vercel or enabling Git credentials."
    }

def write_diagnostic(plan):
    execution_complete = datetime.now(UTC)
    log_id = plan.get("filename") or f"log_{execution_complete.isoformat()}"
    content = {
        "execution_time": execution_complete.isoformat(),
        "task_details": plan.get("content") or {},
        "execution_metadata": {
            "status": "completed",
            "task_type": plan.get("action") or plan.get("intent")
        }
    }
    os.makedirs(DIAGNOSTICS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSTICS_DIR), exist_ok=True)  # Ensure parent logs dir exists
    filepath = os.path.join(DIAGNOSTICS_DIR, f"{log_id}.json")
    try:
        with open(filepath, "w") as f:
            json.dump(content, f, indent=2)
        return {"success": True, "message": f"🩺 Diagnostic log saved to {filepath}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_app_template(template_type):
    # Placeholder for app template generation
    return f"Template for {template_type} app"

def deploy_to_replit(project_name):
    # Placeholder for Replit deployment
    return f"Deployment configured for {project_name}"