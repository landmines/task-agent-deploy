
import json
from typing import List, Dict, Any

def plan_tasks(goal_description: str) -> List[Dict[str, Any]]:
    """
    Break down a high-level goal into executable steps.
    Currently uses predefined templates, can be extended with LLM integration.
    """
    # Basic templates for common scenarios
    templates = {
        "create_app": [
            {
                "intent": "create_app",
                "template_type": "web",
                "project_name": "web-app",
                "provider": "replit"
            },
            {
                "intent": "run_tests",
                "scope": "new_app"
            },
            {
                "intent": "deploy",
                "project_name": "web-app",
                "provider": "replit"
            }
        ],
        "add_feature": [
            {
                "intent": "modify_file",
                "filename": "app.py",
                "change_type": "add_feature"
            },
            {
                "intent": "run_tests",
                "scope": "modified_files"
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
        ]
    }
    
    # Simple keyword matching for now
    if "create" in goal_description.lower() and "app" in goal_description.lower():
        return templates["create_app"]
    elif "add" in goal_description.lower() and "feature" in goal_description.lower():
        return templates["add_feature"]
    
    # Default to single task if no template matches
    return [{
        "intent": "execute",
        "description": goal_description,
        "requires_planning": True
    }]

def validate_plan(steps: List[Dict[str, Any]]) -> bool:
    """Validate that a plan's steps are properly structured"""
    if not steps:
        return False
        
    required_fields = ["intent"]
    valid_intents = {"create_app", "deploy", "modify_file", "run_tests", "create_file", "append_to_file", "delete_file"}
    
    for step in steps:
        # Check required fields
        if not all(field in step for field in required_fields):
            return False
            
        # Validate intent
        if step["intent"] not in valid_intents:
            return False
            
        # Validate provider if deployment
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
        "run_tests": 1
    }
    return risk_levels.get(step["intent"], 2)
