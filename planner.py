
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
                "project_name": "web-app"
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
    required_fields = ["intent"]
    return all(all(field in step for field in required_fields) for step in steps)
