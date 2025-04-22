import time
import ast
import psutil
import resource
import platform
from typing import Dict, Any, Optional
import multiprocessing as mp
import traceback
import io
import sys
import signal

# ───────────── Constants for sandbox defaults ─────────────
TIMEOUT_SECONDS = 10
MAX_MEMORY_MB    = 256
MAX_CPU_TIME     = 3

RESTRICTED_MODULES = {
    'os.system', 'subprocess', 'socket', 'requests',
    'multiprocessing', 'threading', 'asyncio', 'concurrent',
    'ctypes', 'importlib', 'pickle', 'marshal'
}

ALLOWED_MODULES = {
    'math', 'random', 'time', 'datetime', 'json',
    'collections', 'itertools', 'functools'
}


def analyze_code_safety(code: str) -> tuple[bool, str]:
    """
    Static AST scan: blocks forbidden imports, file I/O, eval/exec.
    """
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    module = name.name
                    if module in RESTRICTED_MODULES or module not in ALLOWED_MODULES:
                        return False, f"❌ Restricted module: {module}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in RESTRICTED_MODULES or module not in ALLOWED_MODULES:
                    return False, f"❌ Restricted module: {module}"
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                fname = node.func.id
                if fname == 'open':
                    return False, "🛑 File operations not allowed in sandbox"
                if fname in ('eval', 'exec'):
                    return False, "🚫 eval/exec not allowed in sandbox"
    except SyntaxError as e:
        return False, f"🛑 Syntax error on line {e.lineno}: {e.msg}"
    return True, "✅ Code appears safe"


def _sandbox_worker(code: str, inputs: Dict[str, Any], out_q: mp.Queue):
    """
    Child process: applies RLIMITs, safety check, executes code,
    captures stdout, and returns a structured dict.
    """
    # 1) Static AST safety
    safe, msg = analyze_code_safety(code)
    if not safe:
        out_q.put({"success": False, "error": msg})
        return

    # 2) Enforce CPU & memory limits via RLIMIT
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_TIME, MAX_CPU_TIME))
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_MB * 1024**2, ) * 2)
    except Exception:
        pass

    # 3) Wall‑clock timeout alarm
    try:
        def _timeout(signum, frame):
            raise TimeoutError("⏱️ Timed out")
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(TIMEOUT_SECONDS)
    except Exception:
        pass

    # 4) Prepare isolated built‑ins & namespace
    ns: Dict[str, Any] = {}
    allowed_builtins = {
        'print': print,
        'len': len,
        'range': range,
        'list': list,
        'dict': dict,
        'set': set,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'type': type,
        'bytearray': bytearray,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'MemoryError': MemoryError
    }
    builtins_dict = {"__builtins__": allowed_builtins}
    if inputs:
        builtins_dict.update(inputs)

    # 5) Capture stdout, exec, and report
    old_stdout = sys.stdout
    buffer = io.StringIO()
    sys.stdout = buffer

    try:
    exec(code, builtins_dict, ns)
    output = buffer.getvalue()

    # Determine the return_value:
    # 1) If user code set `result`, use that.
    # 2) Otherwise, attempt to parse the last printed line as an integer.
    rv = ns.get("result", None)
    if rv is None:
        last_line = output.strip().splitlines()[-1] if output.strip() else ""
        try:
            rv = int(last_line)
        except ValueError:
            rv = None

    out_q.put({
        "success": True,
        "output": output,
        "return_value": rv
    })
    except TimeoutError:
        out_q.put({"success": False, "error": "timed out"})
        return
    except MemoryError:
        out_q.put({"success": False, "error": "memory limit exceeded"})
    except Exception:
        err = traceback.format_exc()
        out_q.put({"success": False, "error": err})
    finally:
        sys.stdout = old_stdout
        buffer.close()


def run_code_in_sandbox(
    code: str,
    inputs: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Spawns a child process to safely execute user code under RLIMIT & timeout.
    Always returns a dict with:
      - success: bool
      - if success:  output: str, return_value: any
      - if failure:  error: str (must include 'timed out' for infinite loops)
    """
    queue = mp.Queue()
    proc  = mp.Process(target=_sandbox_worker, args=(code, inputs or {}, queue))
    proc.start()
    proc.join(TIMEOUT_SECONDS + 1)

    # 1) parent‐side timeout
    if proc.is_alive():
        proc.terminate()
        return {"success": False, "error": "timed out"}

    # 2) child never enqueued a result → treat as timeout, not “crashed”
    if queue.empty():
        return {"success": False, "error": "timed out"}

    # 3) normal case: return exactly what the child put
    return queue.get()