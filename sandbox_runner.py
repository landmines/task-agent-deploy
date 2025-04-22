import time
import ast
import psutil
import resource
import platform
from typing import Dict, Any
from contextlib import contextmanager
from typing import Optional
import multiprocessing as mp
import traceback
import io
import sys


# ───────────── Constants for sandbox defaults ─────────────
RESTRICTED_MODULES = [
    'os.system',
    'subprocess',
    'socket',
    'requests',
    'multiprocessing',
    'threading',
    'asyncio',
    'concurrent',
    'ctypes',
    'importlib',
    'pickle',
    'marshal',
]

TIMEOUT_SECONDS = 10
MAX_MEMORY_MB = 256
MAX_CPU_TIME = 3
MAX_DISK_MB = 50

ALLOWED_MODULES = {
    'math',
    'random',
    'time',
    'datetime',
    'json',
    'collections',
    'itertools',
    'functools',
}


class ResourceLimitExceeded(Exception):
    pass


class ResourceMonitor:

    def __init__(self):
        self.process = psutil.Process()
        self._start_time = time.time()
        self._start_cpu = self.process.cpu_times()

    def check_memory_usage(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def check_cpu_time(self) -> float:
        current = self.process.cpu_times()
        return (current.user - self._start_cpu.user) + (current.system -
                                                        self._start_cpu.system)

    def check_disk_usage(self) -> float:
        return psutil.disk_usage('/').used / (1024 * 1024)

    def check_disk_io(self) -> tuple[float, float]:
        io = self.process.io_counters()
        elapsed = time.time() - self._start_time
        read_rate = io.read_bytes / elapsed if elapsed > 0 else 0
        write_rate = io.write_bytes / elapsed if elapsed > 0 else 0
        return read_rate, write_rate


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
    """
    Child process: applies RLIMITs, safety check, executes code,
    and sends back a result dict via out_q.
    """
    # 1) Static AST safety
    safe, msg = analyze_code_safety(code)
    if not safe:
        out_q.put({"success": False, "error": msg})
        return

    # 2) RLIMIT_CPU & RLIMIT_AS inside the child only
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_TIME, MAX_CPU_TIME))
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_MB * 1024**2, ) * 2)
    except:
        pass

    # 3) Optional wall‑clock timeout
    try:
        import signal
        signal.signal(
            signal.SIGALRM, lambda s, f:
            (_ for _ in ()).throw(TimeoutError("⏱️ Timed out")))
        signal.alarm(TIMEOUT_SECONDS)
    except:
        pass

    # 4) Execute in isolated namespace
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
                'ValueError': ValueError,
                'TypeError': TypeError
            }
        }
        if inputs:
            builtins.update(inputs)

    # ─── Capture stdout into a buffer so we can return it in "output" ─────────
    old_stdout = sys.stdout
+    sys.stdout = io.StringIO()
+    try:
+        exec(code, builtins, ns)
+        output = sys.stdout.getvalue()
+        out_q.put({
+            "success": True,
+            "output": output,
+            "return_value": ns.get("result", None)
+        })
+    except TimeoutError as e:
+        # AST safety + RLIMIT may raise our TimeoutError
+        out_q.put({"success": False, "error": "CPU time exceeded"})
+    except MemoryError as e:
+        out_q.put({"success": False, "error": "Memory limit exceeded"})
+    except Exception as e:
+        # any other exception: include its traceback
+        err = traceback.format_exc()
+        out_q.put({"success": False, "error": err})
+    finally:
+        sys.stdout = old_stdout        
        exception:
        out_q.put({"success": False, "error": traceback.format_exc()})


def run_code_in_sandbox(
        code: str,
        inputs: Optional[Dict[str, Any]] = None,
        timeout: int = TIMEOUT_SECONDS,
        memory_limit_mb: int = MAX_MEMORY_MB) -> Dict[str, Any]:
    """
    Spawn a child process to run user code under RLIMIT & timeout,
    so the parent process (pytest/Flask) never gets killed.
    """
    q = mp.Queue()
    p = mp.Process(target=_sandbox_worker, args=(code, inputs or {}, q))
    p.start()
    p.join(timeout + 1)

    if p.is_alive():
        p.terminate()
        return {"success": False, "error": "⏱️ Code execution timed out"}

    if q.empty():
        return {"success": False, "error": "❌ Child crashed or was killed"}

    return q.get()
