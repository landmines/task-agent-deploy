import os
import threading
import logging
import shutil
import difflib
from datetime import datetime, timezone

# ─── STEP 1: DEFINE CORE FILES ─────────────────────────────────────────────
# These files can only be edited when SELF_MODIFY_MODE is enabled.
CORE_FILES = {
    "file_ops.py",
    "task_executor.py",
    # Add any other filenames here, relative to your project root.
}
# ────────────────────────────────────────────────────────────────────────────

# Global lock to prevent race conditions
_file_ops_lock = threading.Lock()

# Constants
PROJECT_ROOT = os.getcwd()
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _backup_file(filepath: str) -> str:
    """Create a timestamped backup and return its path."""
    if not os.path.exists(filepath):
        return ""
    _ensure_backup_dir()
    filename = os.path.basename(filepath)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filename}_BACKUP_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(filepath, backup_path)
    return backup_path


def _validate_filepath(filename: str) -> bool:
    """Disallow absolute or traversal paths."""
    norm = os.path.normpath(filename)
    return not (norm.startswith("/") or norm.startswith("\\") or ".." in norm
                or any(c in norm for c in "<>|*?"))


class FileOps:
    
    @staticmethod
    def patch_code(filename: str, target: str, new_code: str) -> dict:
        """Patch code by inserting new_code after the target line."""
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            backup = _backup_file(full)
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                patched = False
                for line in lines:
                    new_lines.append(line)
                    if not patched and target in line:
                        new_lines.append(new_code + "\n")
                        patched = True
                if not patched:
                    return {"success": False, "message": "Target line not found"}
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                return {
                    "success": True, 
                    "message": f"Patched code in {filename}",
                    "backup": backup
                }
            except Exception as e:
                logging.error(f"patch_code error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def validate_filepath(filename: str) -> bool:
        """
        Returns True if:
         - The path is inside PROJECT_ROOT (no ../ escapes).
         - It doesn’t contain unsafe chars.
         - It isn’t a core file unless SELF_MODIFY_MODE=1.
        """
        # 1) Resolve an absolute path for the target
        full = os.path.abspath(os.path.join(PROJECT_ROOT, filename))

        # 2) Must live under PROJECT_ROOT
        project_root = os.path.abspath(PROJECT_ROOT)
        if not full.startswith(project_root + os.sep):
            return False

        # 3) Disallow unsafe characters in the *relative* part
        rel = os.path.relpath(full, project_root)
        if any(c in rel for c in "<>|*?") or ".." in rel:
            return False

        # 4) Prevent editing core files unless flagged
        if rel in CORE_FILES and os.environ.get("SELF_MODIFY_MODE") != "1":
            return False

        return True

    @staticmethod
    def create_file(filename: str, content: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            backup = _backup_file(full)
            try:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(content)
                return {
                    "success": True,
                    "message": f"File created: {filename}",
                    "backup": backup
                }
            except Exception as e:
                logging.error(f"create_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def append_to_file(filename: str, content: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            backup = _backup_file(full)
            try:
                with open(full, "a", encoding="utf-8") as f:
                    f.write(content)
                # Show only the appended diff
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                diff = ''.join(
                    difflib.unified_diff(
                        lines[:-len(content.splitlines(keepends=True))],
                        lines,
                        fromfile=filename,
                        tofile=filename))
                return {
                    "success": True,
                    "message": f"Appended to: {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"append_to_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def replace_line(filename: str, target: str, replacement: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = [
                    line.replace(target, replacement) for line in lines
                ]
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                diff = ''.join(
                    difflib.unified_diff(lines,
                                         new_lines,
                                         fromfile=filename,
                                         tofile=filename))
                return {
                    "success": True,
                    "message": f"Replaced line in {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"replace_line error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def insert_below(filename: str, target: str, new_line: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                inserted = False
                for line in lines:
                    new_lines.append(line)
                    if not inserted and target in line:
                        new_lines.append(new_line + "\n")
                        inserted = True
                if not inserted:
                    return {"success": False, "message": "Target not found."}
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                diff = ''.join(
                    difflib.unified_diff(lines,
                                         new_lines,
                                         fromfile=filename,
                                         tofile=filename))
                return {
                    "success": True,
                    "message": f"Inserted below in {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"insert_below error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def modify_file(filename: str, old_content: str, new_content: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    data = f.read()
                new_data = data.replace(old_content, new_content)
                if data == new_data:
                    return {
                        "success": False,
                        "message": "No occurrences found."
                    }
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(new_data)
                diff = ''.join(
                    difflib.unified_diff(data.splitlines(keepends=True),
                                         new_data.splitlines(keepends=True),
                                         fromfile=filename,
                                         tofile=filename))
                return {
                    "success": True,
                    "message": f"Modified file: {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"modify_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def delete_file(filename: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                backup = _backup_file(full)
                os.remove(full)
                return {
                    "success": True,
                    "message": f"Deleted file: {filename}",
                    "backup": backup
                }
            except Exception as e:
                logging.error(f"delete_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def patch(filename: str, after_line: str, new_code: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                patched = False
                for line in lines:
                    new_lines.append(line)
                    if not patched and after_line in line:
                        new_lines.extend(new_code.splitlines(keepends=True))
                        patched = True
                if not patched:
                    return {
                        "success": False,
                        "message": "After_line not found."
                    }
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                diff = ''.join(
                    difflib.unified_diff(lines,
                                         new_lines,
                                         fromfile=filename,
                                         tofile=filename))
                return {
                    "success": True,
                    "message": f"Patched code in {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"patch error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def patch(filename: str, after_line: str, new_code: str) -> dict:
        # …existing implementation…
        return {
            "success": True,
            "message": f"Patched code in {filename}",
            "backup": backup,
            "diff": diff
        }
        # …end of patch()…
