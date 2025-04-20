import os
import threading
import logging
import shutil
import difflib
from datetime import datetime, timezone

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
    def create_file(filename: str, content: str) -> dict:
        if not _validate_filepath(filename):
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
        if not _validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            backup = _backup_file(full)
            try:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "a", encoding="utf-8") as f:
                    f.write(content)
                return {
                    "success": True,
                    "message": f"Appended to: {filename}",
                    "backup": backup
                }
            except Exception as e:
                logging.error(f"append_to_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def replace_line(filename: str, target: str, replacement: str) -> dict:
        if not _validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                replaced = False
                for line in lines:
                    if not replaced and target in line:
                        new_lines.append(replacement + "\n")
                        replaced = True
                    else:
                        new_lines.append(line)
                if not replaced:
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
                    "message": f"Line replaced in {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"replace_line error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def insert_below(filename: str, target: str, new_line: str) -> dict:
        if not _validate_filepath(filename):
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
        if not _validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    content = f.read().splitlines(keepends=True)
                if old_content not in ''.join(content):
                    return {
                        "success": False,
                        "message": "Old content not found."
                    }
                backup = _backup_file(full)
                updated = ''.join(content).replace(old_content, new_content)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(updated)
                diff = ''.join(
                    difflib.unified_diff(content,
                                         updated.splitlines(keepends=True),
                                         fromfile=filename,
                                         tofile=filename))
                return {
                    "success": True,
                    "message": f"Modified content in {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"modify_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def delete_file(filename: str) -> dict:
        if not _validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}
        full = os.path.join(PROJECT_ROOT, filename)
        with _file_ops_lock:
            if not os.path.exists(full):
                return {"success": False, "message": "File not found."}
            backup = _backup_file(full)
            try:
                os.remove(full)
                return {
                    "success": True,
                    "message": f"Deleted {filename}",
                    "backup": backup
                }
            except Exception as e:
                logging.error(f"delete_file error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def patch(filename: str, after_line: str, new_code: str) -> dict:
        """
        Apply a code patch by inserting `new_code` after the first occurrence
        of `after_line`. Delegates to insert_below (so you get locking, backup,
        diff, etc. for free).
        """
        return FileOps.insert_below(filename=filename,
                                    target=after_line,
                                    new_line=new_code)
