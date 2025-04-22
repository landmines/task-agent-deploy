#!/usr/bin/env python3
import os
import threading
import logging
import shutil
import difflib
from datetime import datetime, timezone

# ─── CORE FILE PROTECTION ────────────────────────────────────────────────
# Only editable when SELF_MODIFY_MODE=1
CORE_FILES = {
    "file_ops.py",
    "task_executor.py",
    # add any other core filenames here
}

# prevent races
_file_ops_lock = threading.Lock()


def _project_root() -> str:
    """
    The directory under which all safe edits must live,
    based on this script's location.
    """
    return os.path.abspath(os.path.dirname(__file__))


def _ensure_backup_dir() -> str:
    """
    Ensure a <project_root>/backups directory exists and return its path.
    """
    root = _project_root()
    path = os.path.join(root, "backups")
    os.makedirs(path, exist_ok=True)
    return path


def _backup_file(filepath: str) -> str:
    """Copy filepath → backups/NAME_BACKUP_TIMESTAMP, return backup path (or "" if missing)."""
    if not os.path.exists(filepath):
        return ""
    backup_dir = _ensure_backup_dir()
    name = os.path.basename(filepath)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"{name}_BACKUP_{ts}"
    dest = os.path.join(backup_dir, backup_name)
    try:
        shutil.copy2(filepath, dest)
        return dest
    except Exception as e:
        logging.error(f"backup failed for {filepath}: {e}")
        return ""


class FileOps:

    @staticmethod
    def validate_filepath(filename: str) -> bool:
        """
        True if:
          - After resolving under cwd, it's still under cwd.
          - The relative path contains no '..' or unsafe chars.
          - It isn't a core file unless SELF_MODIFY_MODE=1.
        """
        # 1) Resolve to an absolute path
        if os.path.isabs(filename):
            full = os.path.abspath(filename)
        else:
            full = os.path.abspath(os.path.join(_project_root(), filename))

        # 2) Must live under cwd
        root = os.path.abspath(_project_root())
        if not full.startswith(root + os.sep):
            return False

        # 3) Relative path checks
        rel = os.path.relpath(full, root)
        if ".." in rel or any(c in rel for c in "<>|*?"):
            return False

        # 4) Protect core files
        if rel in CORE_FILES and os.environ.get("SELF_MODIFY_MODE") != "1":
            return False

        return True

    @staticmethod
    def create_file(filename: str, content: str) -> dict:
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}

        # resolve same way as validation
        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

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

        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

        with _file_ops_lock:
            backup = _backup_file(full)
            try:
                with open(full, "a", encoding="utf-8") as f:
                    f.write(content)
                # show only appended diff
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                chunk = content.splitlines(keepends=True)
                diff = ''.join(
                    difflib.unified_diff(lines[:-len(chunk)],
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

        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new = [ln.replace(target, replacement) for ln in lines]
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(new)
                diff = ''.join(
                    difflib.unified_diff(lines,
                                         new,
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

        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

        with _file_ops_lock:
            try:
                with open(full, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                out, done = [], False
                for ln in lines:
                    out.append(ln)
                    if not done and target in ln:
                        out.append(new_line + "\n")
                        done = True
                if not done:
                    return {"success": False, "message": "Target not found."}
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(out)
                diff = ''.join(
                    difflib.unified_diff(lines,
                                         out,
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

        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

        with _file_ops_lock:
            try:
                data = open(full, "r", encoding="utf-8").read()
                updated = data.replace(old_content, new_content)
                if data == updated:
                    return {
                        "success": False,
                        "message": "No occurrences found."
                    }
                backup = _backup_file(full)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(updated)
                diff = ''.join(
                    difflib.unified_diff(data.splitlines(keepends=True),
                                         updated.splitlines(keepends=True),
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

        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

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
    def patch_code(filename: str, target: str, new_code: str) -> dict:
        """
        Insert new_code after the first line containing target.
        """
        if not FileOps.validate_filepath(filename):
            return {"success": False, "error": "Invalid filename path."}

        full = filename if os.path.isabs(filename) else os.path.join(
            _project_root(), filename)

        with _file_ops_lock:
            backup = _backup_file(full)
            try:
                lines = open(full, "r", encoding="utf-8").readlines()
                out, done = [], False
                for ln in lines:
                    out.append(ln)
                    if not done and target in ln:
                        out.append(new_code + "\n")
                        done = True
                if not done:
                    return {"success": False, "message": "Target not found."}
                with open(full, "w", encoding="utf-8") as f:
                    f.writelines(out)
                diff = ''.join(
                    difflib.unified_diff(lines,
                                         out,
                                         fromfile=filename,
                                         tofile=filename))
                return {
                    "success": True,
                    "message": f"Patched code in {filename}",
                    "backup": backup,
                    "diff": diff
                }
            except Exception as e:
                logging.error(f"patch_code error: {e}")
                return {"success": False, "error": str(e)}

    @staticmethod
    def patch(filename: str, after_line: str, new_code: str) -> dict:
        """Legacy alias for patch_code."""
        return FileOps.patch_code(filename, after_line, new_code)