
import os
from typing import List, Dict, Any
from datetime import datetime, timezone

def plan_tasks(goal_description: str) -> List[Dict[str, Any]]:
    """Break down a high-level goal into executable steps."""
    templates = {
        "create_app": [
            {
                "intent": "create_app",
                "template_type": "web",
                "project_name": "web-app",
                "framework": "flask"
            },
            {
                "intent": "create_file",
                "filename": "requirements.txt",
                "content": "flask\n"
            },
            {
                "intent": "run_tests",
                "scope": "new_app"
            },
            {
                "intent": "deploy",
                "provider": "replit",
                "requires_confirmation": True
            }
        ],
        "modify_code": [
            {
                "intent": "modify_file",
                "requires_confirmation": True
            },
            {
                "intent": "run_tests",
                "scope": "modified"
            }
        ],
        "deploy_updates": [
            {
                "intent": "run_tests",
                "scope": "all"
            },
            {
                "intent": "deploy",
                "provider": "replit"
            }
        ]
    }

    goal = goal_description.lower()

    # Match templates based on keywords
    if any(word in goal for word in ["create", "new", "generate"]) and "app" in goal:
        return templates["create_app"]
    elif any(word in goal for word in ["modify", "change", "update"]):
        return templates["modify_code"]
    elif "deploy" in goal:
        return templates["deploy_updates"]

    # Default to single task if no template matches
    return [{
        "intent": "execute",
        "description": goal_description,
        "requires_confirmation": True
    }]

def validate_plan(steps: List[Dict[str, Any]]) -> tuple[bool, str]:
    """
    Validate that a plan's steps are properly structured
    Returns: (is_valid, error_message)
    """
    if not steps:
        return False, "Empty plan"

    required_fields = ["intent"]
    valid_intents = {
        "create_app", "deploy", "modify_file", 
        "run_tests", "create_file", "append_to_file", 
        "delete_file", "execute", "execute_code",
        "modify_self", "plan_tasks", "queue_task",
        "verify_deployment", "run_sandbox_test"
    }

    risk_levels = {
        "create_file": 1,
        "append_to_file": 1,
        "modify_file": 2,
        "delete_file": 3,
        "deploy": 2,
        "execute_code": 2,
        "modify_self": 3
    }

    # Track dependencies between steps
    resource_states = {}
    
    for i, step in enumerate(steps):
        # Basic validation
        if not all(field in step for field in required_fields):
            return False, f"Step {i+1} missing required fields"
            
        if step["intent"] not in valid_intents:
            return False, f"Step {i+1} has invalid intent: {step['intent']}"
            
        # Risk assessment
        risk = estimate_risk(step)
        if risk > 2:
            step["confirmationNeeded"] = True
            
        # Resource tracking
        if step["intent"] in ["create_file", "modify_file"]:
            filename = step.get("filename")
            if not filename:
                return False, f"Step {i+1} missing filename"
            resource_states[filename] = step["intent"]
            
        # Dependency validation    
        if step["intent"] == "modify_file":
            filename = step.get("filename")
            if filename not in resource_states:
                return False, f"Step {i+1} modifies non-existent file: {filename}"

    for i, step in enumerate(steps):
        if not all(field in step for field in required_fields):
            return False, f"Step {i+1} missing required fields"
        if step["intent"] not in valid_intents:
            return False, f"Step {i+1} has invalid intent: {step['intent']}"
        if step["intent"] == "deploy":
            if not step.get("provider"):
                step["provider"] = "replit"  # Default to replit
            elif step["provider"] != "replit":
                return False, "Only Replit deployment is supported"
        if step["intent"] in ["modify_file", "create_file", "append_to_file"]:
            if not step.get("filename"):
                return False, f"Step {i+1} missing filename"

    return True, "Plan is valid"

def estimate_risk(step: Dict[str, Any]) -> int:
    """
    Estimate risk level of a task step
    Returns: 0 (safe) to 3 (high risk)
    """
    risk_levels = {
        "create_file": 1,
        "append_to_file": 1,
        "modify_file": 2,
        "delete_file": 3,
        "deploy": 2,
        "run_tests": 1,
        "execute": 2
    }
    return risk_levels.get(step["intent"], 2)
