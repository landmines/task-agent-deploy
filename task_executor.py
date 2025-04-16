import os
import re
import json
from datetime import datetime, UTC
from context_manager import load_memory

PROJECT_ROOT = os.getcwd()
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

def restore_from_backup(backup_path):
    """Restore a file from its backup"""
    if not backup_path or not os.path.exists(backup_path):
        return {"success": False, "error": "Backup file not found"}

    try:
        filename = os.path.basename(backup_path).split("_BACKUP_")[0]
        original_path = os.path.join(PROJECT_ROOT, filename)

        with open(backup_path, "r", encoding="utf-8") as backup_file:
            content = backup_file.read()

        with open(original_path, "w", encoding="utf-8") as original_file:
            original_file.write(content)

        return {
            "success": True,
            "message": f"✅ Restored from backup: {backup_path}",
            "restored_file": original_path
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to restore: {str(e)}"}

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

def execute_code(plan):
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
    except Exception as e:
        return {
            "success": False,
            "error": f"Code execution failed: {str(e)}",
            "details": {
                "timeout": timeout,
                "memory_limit": memory_limit
            }
        }

def estimate_risk(plan):
    """Estimate risk level of a task"""
    risk_levels = {
        "create_file": 1,
        "append_to_file": 1,
        "modify_file": 2,
        "delete_file": 3,
        "deploy": 2,
        "execute": 2,
        "execute_code": 2
    }
    return risk_levels.get(plan.get("action") or plan.get("intent"), 2)

def validate_execution_plan(plan):
    """Validate execution plan before running"""
    if not isinstance(plan, dict):
        return False, "Plan must be a dictionary"

    required_fields = ["action"] if "action" in plan else ["intent"]
    if not all(field in plan for field in required_fields):
        return False, "Missing required fields in plan"

    valid_actions = {
        "patch_code", "modify_file",
        "create_file", "append_to_file", "edit_file", "delete_file",
        "execute_code", "push_changes", "create_app", "deploy", "modify_self"
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

def execute_task(plan):
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
        plan["validation"][
            "retry_count"] = retry_count + 1  # Added to access task_id

    # Cost estimation for various operations
    estimated_cost = 0.0
    if plan.get("uses_gpt"):
        # Calculate GPT costs based on token usage
        input_tokens = len(str(plan.get("prompt",
                                        ""))) / 4  # Approximate tokens
        output_tokens = len(str(plan.get("response", ""))) / 4
        gpt_cost = (input_tokens * 0.00003) + (output_tokens * 0.00006
                                               )  # Current GPT-4 pricing
        estimated_cost += gpt_cost

        # Log GPT usage costs
        memory["cost_tracking"]["api_usage_costs"].append({
            "type":
            "gpt",
            "input_tokens":
            input_tokens,
            "output_tokens":
            output_tokens,
            "cost":
            gpt_cost,
            "timestamp":
            datetime.now(UTC).isoformat()
        })
    if plan.get("deployment"):
        from deployment_manager import DeploymentManager
        dm = DeploymentManager()
        deployment_costs = dm.estimate_deployment_cost({
            "compute_hours":
            24,
            "storage_mb":
            plan.get("storage_mb", 100),
            "bandwidth_mb":
            plan.get("bandwidth_mb", 1000)
        })
        estimated_cost += deployment_costs.get("total_cost", 0.0)

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
    except Exception as e:
        print(f"Warning: Memory initialization failed: {str(e)}")
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
        print(
            f"Ã¢Å¡ Ã¯Â¸Â Warning: This action may incur costs: ${estimated_cost:.2f}"
        )

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

    # Add cost estimation for deployments
    if plan.get("action") == "deploy" or plan.get("intent") == "deploy":
        from deployment_manager import DeploymentManager
        dm = DeploymentManager()

        # Estimate resource usage based on project size
        project_path = plan.get("project_path", ".")
        storage_mb = sum(
            os.path.getsize(os.path.join(root, file))
            for root, _, files in os.walk(project_path)
            for file in files) / (1024 * 1024)

        estimated_costs = dm.estimate_deployment_cost({
            "compute_hours":
            24,  # Initial 24-hour estimate
            "storage_mb":
            max(100, storage_mb * 1.5),  # Add 50% buffer
            "bandwidth_mb":
            plan.get("bandwidth_mb", 1000)
        })

        if not estimated_costs["within_free_tier"]:
            return {
                "success": False,
                "error": "Deployment may incur costs",
                "estimated_costs": estimated_costs,
                "message":
                f"Estimated monthly cost: ${estimated_costs['estimated_monthly']:.2f}",
                "requires_approval": True
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

    # Handle code execution in sandbox
    if plan.get("action") == "execute_code":
        from sandbox_runner import run_code_in_sandbox
        code = plan.get("code", "")
        result = run_code_in_sandbox(code)
        return {
            "success":
            result["success"],
            "message":
            "Code executed in sandbox"
            if result["success"] else result["error"],
            "output":
            result["output"]
        }

    # Require confirmation for high-risk actions
    if risk_level > 2 or plan.get("confirmationNeeded") is True:
        return {
            "success": True,
            "message":
            "Ã¢ÂÂ¸Ã¯Â¸Â Task logged but awaiting user confirmation.",
            "pending": True,
            "confirmationNeeded": True,
            "execution_metadata": {
                "start_time": execution_start.isoformat(),
                "status": "pending_confirmation",
                "task_type": plan.get("action") or plan.get("intent")
            }
        }

    action = plan.get("action") or plan.get("intent")
    result = execute_action(plan)
    task_summary = f"{action} - {plan.get('filename', 'N/A')}"
    if not result["success"]:
        # Auto-generate follow-up task with validation
        follow_up_task = {
            "intent": "fix_failure",
            "original_task": task_summary,
            "error": result.get("error", "Unknown error"),
            "requires_confirmation": True,
            "notes":
            f"Auto-generated fix attempt for failed task: {task_summary}",
            "validation": {
                "original_task_id":
                task_id,
                "retry_count":
                0,
                "max_retries":
                3,
                "success_criteria":
                result.get("success_criteria", ["task_completes"])
            }
        }
        add_next_step(memory, follow_up_task)

        # Record retry attempt in memory
        memory.setdefault("retry_tracking", {})
        memory["retry_tracking"][task_id] = {
            "original_error": result.get("error"),
            "retry_task": follow_up_task,
            "timestamp": datetime.now(UTC).isoformat()
        }
    return result

def create_file(plan):
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
            "message": f"Ã¢Å“â€¦ File created at: {full_path}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def append_to_file(plan):
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
        msg = f"Ã¢Å“â€¦ Appended to file: {full_path}"
        if was_created:
            msg += " (file was auto-created)"
        return {"success": True, "message": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def edit_file(plan):
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
            original = f.read()
        new_content = original
        change_made = False

        match = re.match(r"replace all '(.*)' with '(.*)'", instructions,
                         re.IGNORECASE)
        if match:
            target, repl = match.groups()
            if target in original:
                new_content = original.replace(target, repl)
                change_made = True
            else:
                return {
                    "success": False,
                    "error":
                    f"Ã¢ÂÅ’ Text '{target}' not found for replacement."
                }

        match = re.match(r"delete line containing '(.*)'", instructions,
                         re.IGNORECASE)
        if match:
            keyword = match.group(1)
            lines = new_content.splitlines()
            filtered = [line for line in lines if keyword not in line]
            if len(lines) != len(filtered):
                new_content = "\n".join(filtered) + "\n"
                change_made = True
            else:
                return {
                    "success": False,
                    "error": f"Ã¢ÂÅ’ No lines found containing '{keyword}'"
                }

        match = re.match(r"replace line '(.*)' with '(.*)'", instructions,
                         re.IGNORECASE)
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
                return {
                    "success": False,
                    "error": f"Ã¢ÂÅ’ Exact line '{old_line}' not found."
                }

        if not change_made:
            return {
                "success": False,
                "error":
                "Ã¢ÂÅ’ Could not understand or apply edit instructions."
            }

        backup_path = backup_file(full_path)
        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "success": True,
            "message": f"Ã¢Å“â€¦ File '{filename}' edited.",
            "backup": backup_path,
            "original_file": filename,
            "instructions": instructions,
            "timestamp": datetime.now(UTC).isoformat()
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_file(plan):
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
            "message": f"Ã°Å¸â€”â€˜Ã¯Â¸Â File deleted: {full_path}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def simulate_push():
    return {
        "success": True,
        "message":
        "Ã°Å¸Â§Âª Simulated push: Git command not run (unsupported in current environment).",
        "note": "Try again after migrating to Vercel or enabling Git"
    }


from context_manager import load_memory

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
    filepath = os.path.join(DIAGNOSTICS_DIR, f"{log_id}.json")
    try:
        with open(filepath, "w") as f:
            json.dump(content, f, indent=2)
        return {
            "success": True,
            "message": f"Ã°Å¸Â©Âº Diagnostic log saved to {filepath}"
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

def execute_action(action_plan):
    """Execute actions with consistent status handling"""
    result = {
        "success": False,
        "action": action_plan.get("action"),
        "message": "",
        "timestamp": datetime.now(UTC).isoformat()
    }

    try:
        match action_plan.get("action"):
            case "modify_file":
                result.update(modify_file(action_plan))
            case "create_file":
                result.update(create_file(action_plan))
            case "append_to_file":
                result.update(append_to_file(action_plan))
            case "delete_file":
                result.update(delete_file(action_plan))
            case "execute_code":
                result.update(execute_code(action_plan))
            case "patch_code":
                result.update(patch_code(action_plan))
            case "run_shell":
                command = action_plan.get("command")
                if not command:
                    result["message"] = "Missing shell command"
                else:
                    try:
                        import subprocess
                        output = subprocess.check_output(
                            command,
                            shell=True,
                            stderr=subprocess.STDOUT,
                            timeout=10,
                            text=True
                        )
                        result.update({
                            "success": True,
                            "message": "Shell command executed",
                            "output": output
                        })
                    except subprocess.CalledProcessError as e:
                        result.update({
                            "success": False,
                            "message": "Shell command failed",
                            "error": e.output
                        })
                    except Exception as e:
                        result.update({
                            "success": False,
                            "message": f"Exception during shell execution: {str(e)}"
                        })

            case "run_python":
                code = action_plan.get("code")
                if not code:
                    result["message"] = "Missing Python code"
                else:
                    try:
                        local_vars = {}
                        exec(code, {}, local_vars)
                        result.update({
                            "success": True,
                            "message": "Python code executed",
                            "output": str(local_vars)
                        })
                    except Exception as e:
                        result.update({
                            "success": False,
                            "message": f"Python execution failed: {str(e)}"
                        })
            case _:
                result.update({
                    "success": False,
                    "error": f"Unsupported action: {action_plan.get('action')}"
                })

        return result

    except Exception as e:
        result.update({
            "success": False,
            "error": f"Action execution failed: {str(e)}"
        })
        result.setdefault("execution_metadata", {})
        result["execution_metadata"].update({
            "status": "completed" if result.get("success") else "failed",
            "start_time": result["timestamp"]
        })
        return result

valid_intents = {
    "create_app", "deploy", "modify_file", "run_tests", "create_file",
    "append_to_file", "delete_file", "execute", "execute_code", "modify_self",
    "plan_tasks", "queue_task", "verify_deployment", "run_sandbox_test", "run_shell", "run_python",
    "fix_failure"
}
def patch_code(plan):
    """Patch code with improved validation"""
    try:
        required_fields = ["filename", "function", "after_line", "new_code"]
        missing_fields = [field for field in required_fields if not plan.get(field)]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields for patch_code: {', '.join(missing_fields)}"
            }

        filename = plan["filename"]
        function = plan["function"]
        anchor_line = plan["after_line"]
        new_code = plan["new_code"]

        if not os.path.exists(filename):
            return {
                "success": False,
                "error": f"File not found: {filename}"
            }

        from agent_tools.code_editor import insert_code_after_line_in_function
        result = insert_code_after_line_in_function(filename, function, anchor_line, new_code)

        if result["success"]:
            backup_path = backup_file(filename)
            result["backup"] = backup_path

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Patch code failed: {str(e)}"
        }