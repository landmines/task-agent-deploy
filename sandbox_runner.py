# sandbox_runner.py
import io
import sys
import traceback

def run_in_sandbox(code_str):
    """Safely executes Python code and returns the result or error."""
    # Blocklist for unsafe keywords
    forbidden_keywords = [
        "import os", "import sys", "open(", "exec(", "eval(", "__import__", "subprocess", "input(",
        "shutil", "socket", "requests", "globals(", "locals(", "compile(", "memoryview", "del", "lambda"
    ]

    # Basic guard clause
    for word in forbidden_keywords:
        if word in code_str:
            return {
                "success": False,
                "error": f"❌ Blocked unsafe keyword: '{word}'"
            }

    # Redirect stdout to capture print output
    stdout_backup = sys.stdout
    stderr_backup = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

    # Safe namespace
    safe_globals = {"__builtins__": {
        "print": print,
        "range": range,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "enumerate": enumerate,
        "zip": zip,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs
    }}

    try:
        exec(code_str, safe_globals)
        output = sys.stdout.getvalue()
        error = sys.stderr.getvalue()
        return {
            "success": True,
            "output": output.strip(),
            "error": error.strip() if error else None
        }
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "success": False,
            "error": f"❌ Exception: {str(e)}",
            "traceback": tb
        }
    finally:
        # Restore stdout/stderr
        sys.stdout = stdout_backup
        sys.stderr = stderr_backup
