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

# Constants for sandbox defaults
TIMEOUT_SECONDS = 10
MAX_MEMORY_MB = 256
MAX_CPU_TIME = 3

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
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    m = name.name
                    if m in RESTRICTED_MODULES or m not in ALLOWED_MODULES:
                        return False, f"❌ Restricted module: {m}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in RESTRICTED_MODULES or mod not in ALLOWED_MODULES:
                    return False, f"❌ Restricted module: {mod}"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == 'open':
                        return False, "🛑 File operations not allowed in sandbox"
                    if node.func.id in ('eval', 'exec'):
                        return False, "🚫 eval/exec not allowed in sandbox"
    except SyntaxError as e:
        return False, f"🛑 Syntax error on line {e.lineno}: {e.msg}"
    return True, "✅ Code appears safe"

def _sandbox_worker(code: str, inputs: Dict[str, Any], out_q: mp.Queue):
    """Child process: applies RLIMITs, safety check, executes code"""
    # Static AST safety
    safe, msg = analyze_code_safety(code)
    if not safe:
        out_q.put({"success": False, "error": msg})
        return

    # RLIMIT_CPU & RLIMIT_AS inside the child only
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_TIME, MAX_CPU_TIME))
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_MB * 1024**2, ) * 2)
    except:
        pass

    # Wall‑clock timeout
    try:
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("⏱️ Timed out")
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(TIMEOUT_SECONDS)
    except:
        pass

    # Execute in isolated namespace
    try:
        ns: Dict[str, Any] = {}
        builtins = {
            "__builtins__": {
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
        }
        if inputs:
            builtins.update(inputs)

        # Capture stdout
        old_stdout = sys.stdout
        string_out = io.StringIO()
        sys.stdout = string_out

        try:
            exec(code, builtins, ns)
            output = string_out.getvalue()
            out_q.put({
                "success": True,
                "output": output,
                "return_value": ns.get("result", None)
            })
        except TimeoutError:
            out_q.put({"success": False, "error": "⏱️ Code execution timed out"})
        except MemoryError:
            out_q.put({"success": False, "error": "Memory limit exceeded"})
        except Exception as e:
            out_q.put({"success": False, "error": traceback.format_exc()})
        finally:
            sys.stdout = old_stdout
            string_out.close()
    except Exception as e:
        out_q.put({"success": False, "error": traceback.format_exc()})

def run_code_in_sandbox(code: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Spawn a child process to run user code under RLIMIT & timeout"""
    q = mp.Queue()
    p = mp.Process(target=_sandbox_worker, args=(code, inputs or {}, q))
    p.start()
    p.join(TIMEOUT_SECONDS + 1)

    if p.is_alive():
        p.terminate()
        return {"success": False, "error": "⏱️ Code execution timed out"}

    if q.empty():
        return {"success": False, "error": "❌ Child crashed or was killed"}

    return q.get()