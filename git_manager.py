
import os
import subprocess
from datetime import datetime, UTC

def commit_changes(message, files=None):
    """Commit changes to git repository with memory tracking"""
    try:
        # Create backup of modified files
        if files:
            for file in files:
                backup_file(file)
            subprocess.run(["git", "add"] + files, check=True)
        else:
            subprocess.run(["git", "add", "-A"], check=True)
            
        # Execute commit
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        pre_commit_hash = result.stdout.strip()
        
        subprocess.run(["git", "commit", "-m", message], check=True)
        
        # Get new commit hash
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        commit_hash = result.stdout.strip()
        
        # Store commit metadata in memory
        from context_manager import load_memory, save_memory_context
        memory = load_memory()
        memory.setdefault("git_commits", [])
        
        commit_meta = {
            "hash": commit_hash,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
            "files": files or [],
            "previous_hash": pre_commit_hash
        }
        
        memory["git_commits"].append(commit_meta)
        memory["last_commit"] = commit_meta
        save_memory_context(memory)

def backup_file(filepath):
    """Create a backup of a file before modification"""
    import shutil
    from datetime import datetime, UTC
    
    if not os.path.exists(filepath):
        return None
        
    backup_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{os.path.basename(filepath)}.{timestamp}.bak")
    
    shutil.copy2(filepath, backup_path)
    return backup_path

def rollback_changes(commit_hash=None):
    """Rollback to a specific commit or the last commit"""
    try:
        if commit_hash:
            subprocess.run(["git", "reset", "--hard", commit_hash], check=True)
        else:
            subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)
        return {"success": True, "message": "Changes rolled back successfully"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"Failed to rollback: {str(e)}"}
            
        return {"success": True, "message": f"✅ Changes committed: {message}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"Git commit failed: {str(e)}"}
    
    return {"success": True, "message": f"✅ Changes committed: {message}"}

def revert_last_commit():
    """Revert the last commit"""
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)
        return {"success": True, "message": "✅ Reverted last commit"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"Git revert failed: {str(e)}"}

def get_commit_history(limit=10):
    """Get recent commit history"""
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--oneline"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError:
        return []
