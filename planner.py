import os
from typing import List, Dict, Any
from datetime import datetime, UTC

def plan_tasks(goal_description: str) -> List[Dict[str, Any]]:
    """Break down a high-level goal into executable steps."""
    templates = {
        "create_app": [
            {
                "intent": "create_app",
                "template_type": "web",
                "project_name": "web-app"
            },
            {
                "intent": "run_tests",
                "scope": "new_app"
            },
            {
                "intent": "deploy",
                "provider": "replit"
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

def validate_plan(steps: List[Dict[str, Any]]) -> bool:
    """Validate that a plan's steps are properly structured"""
    if not steps:
        return False

    required_fields = ["intent"]
    valid_intents = {
        "create_app", "deploy", "modify_file", 
        "run_tests", "create_file", "append_to_file", 
        "delete_file", "execute"
    }

    for step in steps:
        if not all(field in step for field in required_fields):
            return False
        if step["intent"] not in valid_intents:
            return False
        if step["intent"] == "deploy" and step.get("provider") != "replit":
            return False

    return True

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