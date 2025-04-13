
import os
import subprocess
from datetime import datetime, UTC

def commit_changes(message, files=None):
    """Commit changes to git repository"""
    try:
        if files:
            subprocess.run(["git", "add"] + files, check=True)
        else:
            subprocess.run(["git", "add", "-A"], check=True)
            
        subprocess.run(["git", "commit", "-m", message], check=True)
        return {"success": True, "message": f"✅ Changes committed: {message}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"Git commit failed: {str(e)}"}

def revert_last_commit():
    """Revert the last commit"""
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)
        return {"success": True, "message": "✅ Reverted last commit"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"Git revert failed: {str(e)}"}
