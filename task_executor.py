import os
import re
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, UTC
from context_manager import load_memory

PROJECT_ROOT = os.getcwd()
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
DIAGNOSTICS_DIR = os.path.join(PROJECT_ROOT, "logs", "diagnostics")

def backup_file(filepath: str) -> Optional[str]:
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

def restore_from_backup(backup_path: str) -> Dict[str, Any]:
    """Restore a file from its backup"""
    if not backup_path or not os.path.exists(backup_path):
        return {"success": False, "error": "Backup file not found"}

    try:
        filename = os.path.basename(backup_path).split("_BACKUP_")[0]
        original_path = os.path.join(PROJECT_ROOT, filename)

        # Reading from the backup file
        with open(backup_path, "r", encoding="utf-8") as backup_file:
            content = backup_file.read()

        # Writing to the original file
        with open(original_path, "w", encoding="utf-8") as original_file:
            original_file.write(content)

        return {
            "success": True,
            "message": f"✅ Restored from backup: {backup_path}",
            "restored_file": original_path
        }

    # If backup file doesn't exist
    except FileNotFoundError:
        logging.error(f"Backup file not found: {backup_path}")
        return {
            "success": False,
            "error": f"Backup file not found: {backup_path}"
        }

    # Permission issue reading or writing file
    except PermissionError:
        logging.error(f"Permission denied accessing files: {backup_path} or {original_path}")
        return {
            "success": False,
            "error": "Permission denied accessing backup or original file."
        }

    # General I/O problems (disk errors, corrupted file)
    except (IOError, OSError) as e:
        logging.error(f"I/O error restoring backup: {str(e)}")
        return {
            "success": False,
            "error": f"I/O error occurred: {str(e)}"
        }

def modify_file(plan):
    """Modify existing file content with proper validation"""
    filename = plan.get("filename")
    old_content = plan.get("old_content")
    new_content = plan.get("new_content")

    if not all([filename, old_content, new_content]):
        return {"success": False, "error": "Missing required fields"}

    if not isinstance(filename, str) or not isinstance(old_content, str) or not isinstance(new_content, str):
        return {"success": False, "error": "Invalid data types provided"}

    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File {filename} not found"}

    try:
        with open(full_path, "r") as f:
            content = f.read()

        if old_content not in content:
            return {"success": False, "error": "Old content not found in file"}

        backup_path = backup_file(full_path)
        if not backup_path:
            return {"success": False, "error": "Failed to create backup"}

        new_content_full = content.replace(old_content, new_content)
        with open(full_path, "w") as f:
            f.write(new_content_full)

        return {
            "success": True,
            "message": f"File modified: {filename}",
            "backup": backup_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_code(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Execute code in sandbox environment with proper resource limits"""
    code = plan.get("code")
    inputs = plan.get("inputs", {})
    timeout = min(plan.get("timeout", 5), 30)  # Cap at 30 seconds
    memory_limit = min(plan.get("memory_limit", 100 * 1024 * 1024), 512 * 1024 * 1024)  # Cap at 512MB

    if not code:
        return {"success": False, "error": "No code provided"}

    try:
        from sandbox_runner import run_code_in_sandbox
        result = run_code_in_sandbox(
            code,
            timeout=timeout,
            memory_limit=memory_limit,
            inputs=inputs
        )
        return result

    except ModuleNotFoundError:
        logging.error("Sandbox runner module 'sandbox_runner' is not found.")
        return {
            "success": False,
            "error": "Sandbox execution module not found. Ensure it's correctly installed.",
            "details": {
                "timeout": timeout,
                "memory_limit": memory_limit
            }
        }

    except RuntimeError as e:
        logging.error(f"Runtime error during sandbox code execution: {str(e)}")
        return {
            "success": False,
            "error": f"Runtime error during code execution: {str(e)}",
            "details": {
                "timeout": timeout,
                "memory_limit": memory_limit
            }
        }

    except Exception as e:
        logging.error(f"Unexpected error during sandbox execution: {str(e)}")
        return {
            "success": False,
            "error": "Unexpected error during sandbox execution.",
            "details": {
                "error_message": str(e),
                "timeout": timeout,
                "memory_limit": memory_limit
            }
        }

def estimate_risk(plan: Dict[str, Any]) -> int:
    """Estimate risk level of a task"""
    risk_levels = {
        "create_file": 1,
        "append_to_file": 1,
        "modify_file": 2,
        "delete_file": 3,
        "deploy": 2,
        "execute": 2,
        "execute_code": 2,
        "patch_code": 2
    }
    return risk_levels.get(plan.get("action") or plan.get("intent"), 2)

def validate_execution_plan(plan: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate execution plan before running"""
    if not isinstance(plan, dict):
        return False, "Plan must be a dictionary"

    required_fields = ["action"] if "action" in plan else ["intent"]
    if not all(field in plan for field in required_fields):
        return False, "Missing required fields in plan"

    valid_actions = {
        "patch_code", "modify_file",
        "create_file", "append_to_file", "edit_file", "delete_file",
        "execute_code", "push_changes", "create_app", "deploy", "modify_self",
        "create_and_run", "confirm_latest"
    }

    action = plan.get("action") or plan.get("intent")
    if action not in valid_actions:
        return False, f"Invalid action: {action}"

    # Validate file operations
    if action in ["create_file", "append_to_file", "edit_file", "delete_file"]:
        filename = plan.get("filename")
        if not filename:
            return False, "Missing filename"
        if ".." in filename or filename.startswith("/"):
            return False, "Invalid filename path"

    # Validate code execution
    if action == "execute_code":
        if not plan.get("code"):
            return False, "Missing code to execute"

    # Validate deployment
    if action == "deploy":
        if not plan.get("project_name"):
            return False, "Missing project name for deployment"

    return True, None

def execute_task(plan: Dict[str, Any]) -> Dict[str, Any]:
    execution_start = datetime.now(UTC)
    risk_level = estimate_risk(plan)
    task_id = plan.get("task_id")

    # Handle retry validation
    if plan.get("intent") == "fix_failure":
        validation = plan.get("validation", {})
        retry_count = validation.get("retry_count", 0)

        if retry_count >= validation.get("max_retries", 3):
            return {
                "success": False,
                "error": "Maximum retry attempts reached",
                "requires_manual_intervention": True
            }

        # Update retry count
        plan["validation"]["retry_count"] = retry_count + 1

    # Cost estimation for various operations
    estimated_cost = 0.0
    if plan.get("uses_gpt"):
        # Calculate GPT costs based on token usage
        input_tokens = len(str(plan.get("prompt", ""))) / 4  # Approximate tokens
        output_tokens = len(str(plan.get("response", ""))) / 4
        gpt_cost = (input_tokens * 0.00003) + (output_tokens * 0.00006)  # Current GPT-4 pricing
        estimated_cost += gpt_cost

    # Update cost tracking in memory
    
    try:
        memory = load_memory()
        if not isinstance(memory, dict):
            memory = {}

        # Ensure cost_tracking is initialized
        if "cost_tracking" not in memory:
            memory["cost_tracking"] = {
                "total_estimated": 0.0,
                "api_usage_costs": [],
                "last_updated": None
            }

    except FileNotFoundError:
        logging.warning("Memory file not found. Initializing new memory.")
        memory = {
            "cost_tracking": {
                "total_estimated": 0.0,
                "api_usage_costs": [],
                "last_updated": None
            }
        }

    except json.JSONDecodeError:
        logging.warning("Memory file is not valid JSON. Initializing new memory.")
        memory = {
            "cost_tracking": {
                "total_estimated": 0.0,
                "api_usage_costs": [],
                "last_updated": None
            }
        }

    except TypeError:
        logging.warning("Loaded memory is not a dictionary. Resetting.")
        memory = {
            "cost_tracking": {
                "total_estimated": 0.0,
                "api_usage_costs": [],
                "last_updated": None
            }
        }

    except Exception as e:
        logging.error(f"Unexpected error loading memory: {str(e)}")
        memory = {
            "cost_tracking": {
                "total_estimated": 0.0,
                "api_usage_costs": [],
                "last_updated": None
            }
        }
    
    memory["cost_tracking"]["total_estimated"] += estimated_cost
    memory["cost_tracking"]["last_updated"] = datetime.now(UTC).isoformat()

    # Enforce cost thresholds and warn if costs exceed free tier
    if estimated_cost > 0:
        print(f"⚠️ Warning: This action may incur costs: ${estimated_cost:.2f}")

        # Hard threshold - block actions over $10
        if estimated_cost > 10.0:
            return {
                "success": False,
                "error": "Action exceeds maximum cost threshold ($10)",
                "estimated_cost": estimated_cost,
                "requires_confirmation": False,
                "blocked": True
            }

        # Require confirmation for any paid actions
        if not plan.get("cost_confirmed"):
            return {
                "success": False,
                "error": "Action requires cost confirmation",
                "estimated_cost": estimated_cost,
                "requires_confirmation": True,
                "warning": f"This action will cost ${estimated_cost:.2f}"
            }

    # Validate plan before execution
    is_valid, error = validate_execution_plan(plan)
    if not is_valid:
        return {
            "success": False,
            "error": error,
            "execution_metadata": {
                "start_time": execution_start.isoformat(),
                "status": "validation_failed"
            }
        }

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

    # Execute the action
    result = execute_action(plan)

    # Add execution metadata
    result["execution_metadata"] = {
        "start_time": execution_start.isoformat(),
        "end_time": datetime.now(UTC).isoformat(),
        "status": "completed" if result.get("success") else "failed",
        "task_type": plan.get("action") or plan.get("intent")
    }

    return result

def create_file(plan: Dict[str, Any]) -> Dict[str, Any]:
    filename = plan.get("filename")
    content = plan.get("content", "")
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return {"success": False, "error": "Invalid filename."}
    full_path = os.path.join(PROJECT_ROOT, filename)
    try:
        with open(full_path, "w") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"✅ File created at: {full_path}"
        }

    except PermissionError:
        logging.error(f"Permission denied when trying to write to: {full_path}")
        return {
            "success": False,
            "error": f"Permission denied: {full_path}"
        }

    except (IOError, OSError) as e:
        logging.error(f"I/O error while writing to {full_path}: {str(e)}")
        return {
            "success": False,
            "error": f"I/O error: {str(e)}"
        }

    except Exception as e:
        logging.error(f"Unexpected error during file creation: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

def append_to_file(plan: Dict[str, Any]) -> Dict[str, Any]:
    filename = plan.get("filename")
    content = plan.get("content", "")
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
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

    except PermissionError:
        logging.error(f"Permission denied writing to: {full_path}")
        return {"success": False, "error": f"Permission denied: {full_path}"}

    except (IOError, OSError) as e:
        logging.error(f"I/O error while appending to {full_path}: {str(e)}")
        return {"success": False, "error": f"I/O error: {str(e)}"}

    except Exception as e:
        logging.error(f"Unexpected error appending to file: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

def edit_file(plan: Dict[str, Any]) -> Dict[str, Any]:
    filename = plan.get("filename")
    instructions = plan.get("instructions", "")
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return {"success": False, "error": "Invalid filename."}
    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {
            "success": False,
            "error": f"File '{full_path}' does not exist. Cannot edit."
        }
    try:
        with open(full_path, "r") as f:
            content = f.read()

        if old_content not in content:
            return {"success": False, "error": "Old content not found in file"}

        backup_path = backup_file(full_path)
        if not backup_path:
            return {"success": False, "error": "Failed to create backup"}

        new_content_full = content.replace(old_content, new_content)
        with open(full_path, "w") as f:
            f.write(new_content_full)

        return {
            "success": True,
            "message": f"File modified: {filename}",
            "backup": backup_path
        }

    except FileNotFoundError:
        logging.error(f"File not found: {full_path}")
        return {"success": False, "error": f"File not found: {filename}"}

    except PermissionError:
        logging.error(f"Permission denied modifying file: {full_path}")
        return {"success": False, "error": f"Permission denied for {filename}"}

    except (IOError, OSError) as e:
        logging.error(f"I/O error modifying file {filename}: {str(e)}")
        return {"success": False, "error": f"I/O error: {str(e)}"}

    except Exception as e:
        logging.error(f"Unexpected error modifying file: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

def delete_file(plan: Dict[str, Any]) -> Dict[str, Any]:
    filename = plan.get("filename")
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return {"success": False, "error": "Invalid filename."}
    full_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(full_path):
        return {
            "success": False,
            "error": f"File '{full_path}' not found. Nothing to delete."
        }
    try:
        os.remove(full_path)
        return {
            "success": True,
            "message": f"🗑️ File deleted: {full_path}"
        }

    except FileNotFoundError:
        logging.warning(f"File to delete not found: {full_path}")
        return {"success": False, "error": f"File '{filename}' not found."}

    except PermissionError:
        logging.error(f"Permission denied deleting: {full_path}")
        return {"success": False, "error": f"Permission denied for file '{filename}'."}

    except (IOError, OSError) as e:
        logging.error(f"I/O error deleting file '{filename}': {str(e)}")
        return {"success": False, "error": f"I/O error: {str(e)}"}

    except Exception as e:
        logging.error(f"Unexpected error deleting file '{filename}': {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

    except Exception as e:
        logging.error(f"Unexpected error editing file '{filename}': {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

def simulate_push():
    return {
        "success": True,
        "message": "🚀 Simulated push: Git command not run (unsupported in current environment).",
        "note": "Try again after migrating to Vercel or enabling Git"
    }

def write_diagnostic(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Write diagnostic information to a log file"""
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
    filepath = os.path.join(DIAGNOSTICS_DIR, f"{log_id}.json")
    try:
        with open(filepath, "w") as f:
            json.dump(content, f, indent=2)
        return {
            "success": True,
            "message": f"✅ Diagnostic log saved to {filepath}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_app_template(template_type):
    # Placeholder for app template generation
    return f"Template for {template_type} app"

def deploy_to_replit(project_name, config=None):
    """Deploy project to Replit with proper configuration"""
    try:
        if not project_name:
            return {
                "success": False,
                "error": "Project name is required"
            }

        config = config or {}
        config.setdefault("port", 5000)
        config.setdefault("start_command", "python app.py")

        # Create or update deployment configuration
        deploy_config = {
            "name": project_name,
            "run_command": config["start_command"],
            "env": config.get("env", {}),
            "port": config["port"]
        }

        # Write deployment configuration
        with open(".replit", "w") as f:
            json.dump(deploy_config, f, indent=2)

        return {
            "success": True,
            "message": f"Deployment configured for {project_name}",
            "config": deploy_config
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Deployment configuration failed: {str(e)}"
        }

def validate_filepath(filename: str) -> bool:
    """Validate if a filepath is safe"""
    import os.path
    if not filename or not isinstance(filename, str):
        return False
    norm_path = os.path.normpath(filename)
    return not (
        ".." in norm_path or
        norm_path.startswith("/") or
        norm_path.startswith("\\") or
        any(c in norm_path for c in ["<", ">", "|", "*", "?"])
    )

def patch_code(plan: dict) -> dict:
    """Patch existing code with new implementation"""
    filename = plan.get("filename")
    if not validate_filepath(filename):
        return {"success": False, "error": "Invalid filename"}

    function_name = plan.get("function")
    new_code = plan.get("new_code")
    after_line = plan.get("after_line")

    if not all([function_name, new_code, after_line]):
        return {"success": False, "error": "Missing required fields"}

    try:
        backup_path = backup_file(filename)
        with open(filename, "r") as f:
            content = f.readlines()

        for i, line in enumerate(content):
            if after_line in line:
                content.insert(i + 1, new_code + "\n")
                break
        else:
            return {"success": False, "error": "Target line not found"}

        with open(filename, "w") as f:
            f.writelines(content)

        return {
            "success": True,
            "message": f"Code patched in {filename}",
            "backup": backup_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_action(plan: dict) -> dict:
    """Execute actions with consistent status handling"""
    result = {
        "success": False,
        "action": plan.get("action"),
        "message": "",
        "timestamp": datetime.now(UTC).isoformat()
    }

    try:
        action = plan.get("action") or plan.get("intent")
        if not isinstance(action, str):
            return {"success": False, "error": "Invalid action type"}

        action_handlers = {
            "modify_file": modify_file,
            "create_file": create_file,
            "append_to_file": append_to_file,
            "delete_file": delete_file,
            "execute_code": execute_code,
            "patch_code": patch_code
        }

        if action in action_handlers:
            result.update(action_handlers[action](plan))
        elif action == "create_and_run":
            try:
                from base64 import b64decode
                import subprocess

                if "code" not in plan or "filename" not in plan:
                    raise ValueError("Missing required fields: code and filename")

                try:
                    code = b64decode(plan["code"]).decode("utf-8")
                except Exception as e:
                    raise ValueError(f"Invalid base64 encoding: {str(e)}")

                filename = os.path.join(PROJECT_ROOT, plan["filename"])
                if not validate_filepath(plan["filename"]):
                    raise ValueError("Invalid filename path")

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(code)

                if plan.get("run_after", False):
                    run_output = subprocess.check_output(
                        ["python", filename],
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=30  # Add timeout
                    )
                    result.update({
                        "success": True,
                        "message": f"✅ File '{filename}' created and executed successfully",
                        "output": run_output
                    })
                else:
                    result.update({
                        "success": True,
                        "message": f"✅ File '{filename}' created successfully"
                    })
            except subprocess.TimeoutExpired:
                result.update({
                    "success": False,
                    "error": "Execution timed out after 30 seconds"
                })
            except Exception as e:
                result.update({
                    "success": False,
                    "error": f"create_and_run failed: {str(e)}"
                })
        else:
            result.update({
                "success": False,
                "error": f"Unsupported action: {action}"
            })

        return result

    except (ValueError, TypeError) as e:
        result.update({
            "success": False,
            "error": f"Invalid input parameters: {str(e)}",
            "error_type": "validation_error"
        })
        return result
    except Exception as e:
        result.update({
            "success": False,
            "error": f"Action execution failed: {str(e)}",
            "error_type": "execution_error"
        })
        return result