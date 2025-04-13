import os
import sys
import time
import psutil
import resource
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
        """Return memory usage in MB"""
        return self.process.memory_info().rss / (1024 * 1024)

    def check_cpu_time(self) -> float:
        """Return CPU time used in seconds"""
        current = self.process.cpu_times()
        return (current.user - self._start_cpu.user) + (current.system - self._start_cpu.system)

    def check_disk_usage(self) -> float:
        """Return disk usage in MB"""
        return psutil.disk_usage('/').used / (1024 * 1024)

    def check_disk_io(self) -> tuple[float, float]:
        """Return disk I/O in bytes/sec (read, write)"""
        io = self.process.io_counters()
        elapsed = time.time() - self._start_time
        read_rate = io.read_bytes / elapsed if elapsed > 0 else 0
        write_rate = io.write_bytes / elapsed if elapsed > 0 else 0
        return read_rate, write_rate

@contextmanager
def resource_limits(max_cpu_time: int = 5, max_memory_mb: int = 100):
    """Set resource limits for the code execution"""
    # Set CPU time limit
    resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_time, max_cpu_time))
    # Set memory limit (in bytes)
    memory_bytes = max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    try:
        yield
    finally:
        # Reset limits to default
        resource.setrlimit(resource.RLIMIT_CPU, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))

def run_code_in_sandbox(code: str, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute code in a sandboxed environment with resource monitoring"""
    monitor = ResourceMonitor()
    result = {
        "success": False,
        "output": "",
        "error": None,
        "resource_usage": {}
    }

    # Create restricted globals
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

    # Add any provided inputs to globals
    if inputs:
        safe_globals.update(inputs)

    try:
        with resource_limits():
            # Execute code in restricted environment
            exec(code, safe_globals, {})

            # Collect resource usage
            result["resource_usage"] = {
                "memory_mb": monitor.check_memory_usage(),
                "cpu_time": monitor.check_cpu_time(),
                "disk_usage_mb": monitor.check_disk_usage(),
                "disk_io": monitor.check_disk_io()
            }

            result["success"] = True

    except resource.error as e:
        result["error"] = f"Resource limit exceeded: {str(e)}"
        raise ResourceLimitExceeded(result["error"])
    except Exception as e:
        result["error"] = f"Execution failed: {str(e)}"

    return result

RESTRICTED_MODULES = [
    'os.system', 'subprocess', 'socket', 'requests', 
    'multiprocessing', 'threading', 'asyncio', 'concurrent',
    'ctypes', 'importlib', 'pickle', 'marshal'
]
TIMEOUT_SECONDS = 10
MAX_MEMORY_MB = 256
MAX_CPU_TIME = 3  # seconds
MAX_DISK_MB = 50
ALLOWED_MODULES = {
    'math', 'random', 'time', 'datetime', 'json',
    'collections', 'itertools', 'functools'
}

def analyze_code_safety(code: str) -> tuple[bool, str]:
    """
    Check if code contains potentially unsafe operations
    Returns: (is_safe, reason)
    """
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name in RESTRICTED_MODULES:
                        return False, f"Restricted module: {name.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module in RESTRICTED_MODULES:
                    return False, f"Restricted module: {node.module}"

            # Check for file operations
            elif isinstance(node, (ast.Open, ast.Call)) and isinstance(node.func, ast.Name):
                if node.func.id == 'open':
                    return False, "File operations not allowed in sandbox"

            # Check for eval/exec
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['eval', 'exec']:
                    return False, "eval/exec not allowed in sandbox"

    except SyntaxError as e:
        return False, f"Syntax error: {str(e)}"

    return True, "Code appears safe"

@contextmanager
def timeout_handler(seconds: int):
    """Handle timeout for code execution"""
    def timeout_error(signum, frame):
        raise TimeoutError("Code execution timed out")

    # Set the timeout
    import signal
    signal.signal(signal.SIGALRM, timeout_error)
    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)

import ast