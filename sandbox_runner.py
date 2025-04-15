import os
import ast
import psutil
import resource
import platform
from typing import Dict, Any
from contextlib import contextmanager


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


@contextmanager
def resource_limits(max_cpu_time: int = 5, max_memory_mb: int = 100):
    resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_time, max_cpu_time))
    memory_bytes = max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_CPU,
                           (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_AS,
                           (resource.RLIM_INFINITY, resource.RLIM_INFINITY))


@contextmanager
def timeout_handler(seconds: int):
    if platform.system() != 'Windows':
        import signal

        def timeout_error(signum, frame):
            raise TimeoutError("⏱️ Code execution timed out")

        signal.signal(signal.SIGALRM, timeout_error)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
    else:
        yield


def analyze_code_safety(code: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name in RESTRICTED_MODULES:
                        return False, f"❌ Restricted module: {name.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module in RESTRICTED_MODULES:
                    return False, f"❌ Restricted module: {node.module}"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['open']:
                        return False, "🛑 File operations not allowed in sandbox"
                    if node.func.id in ['eval', 'exec']:
                        return False, "🚫 eval/exec not allowed in sandbox"
    except SyntaxError as e:
        return False, f"🛑 Syntax error on line {e.lineno}: {e.msg}"
    return True, "✅ Code appears safe"


def run_code_in_sandbox(code: str,
                        inputs: Dict[str, Any] = None,
                        timeout: int = 5,
                        memory_limit_mb: int = 100) -> Dict[str, Any]:
    monitor = ResourceMonitor()
    result = {
        "success": False,
        "output": "",
        "error": None,
        "return_value": None,
        "resource_usage": {}
    }

    safe_globals = {
        '__builtins__': {
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
        safe_globals.update(inputs)

    try:
        is_safe, safety_msg = analyze_code_safety(code)
        if not is_safe:
            raise ValueError(safety_msg)

        with timeout_handler(timeout):
            with resource_limits(timeout, memory_limit_mb):
                local_vars = {}
                exec(code, safe_globals, local_vars)

                result["output"] = ""
                result["return_value"] = local_vars.get("result", None)
                result["resource_usage"] = {
                    "memory_mb": monitor.check_memory_usage(),
                    "cpu_time": monitor.check_cpu_time(),
                    "disk_usage_mb": monitor.check_disk_usage(),
                    "disk_io": monitor.check_disk_io()
                }
                result["success"] = True

    except resource.error as e:
        result["error"] = f"🚫 Resource limit exceeded: {str(e)}"
        raise ResourceLimitExceeded(result["error"])
    except SyntaxError as e:
        result["error"] = f"🛑 Syntax error on line {e.lineno}: {e.msg}"
    except TimeoutError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"❌ Execution failed: {str(e)}"

    return result


RESTRICTED_MODULES = [
    'os.system', 'subprocess', 'socket', 'requests', 'multiprocessing',
    'threading', 'asyncio', 'concurrent', 'ctypes', 'importlib', 'pickle',
    'marshal'
]
TIMEOUT_SECONDS = 10
MAX_MEMORY_MB = 256
MAX_CPU_TIME = 3
MAX_DISK_MB = 50
ALLOWED_MODULES = {
    'math', 'random', 'time', 'datetime', 'json', 'collections', 'itertools',
    'functools'
}
