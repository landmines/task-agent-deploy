
import os
import sys
import ast
import time
from typing import Dict, Any
from contextlib import contextmanager

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

class ResourceMonitor:
    """Monitor and limit resource usage during code execution"""
    @staticmethod
    def check_memory_usage():
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        if memory_mb > MAX_MEMORY_MB:
            raise ResourceLimitExceeded(f"Memory usage exceeded {MAX_MEMORY_MB}MB limit")
        return memory_mb

    @staticmethod
    def check_disk_usage(path="."):
        import psutil
        disk_usage = psutil.disk_usage(path)
        used_mb = disk_usage.used / (1024 * 1024)
        if used_mb > MAX_DISK_MB:
            raise ResourceLimitExceeded(f"Disk usage exceeded {MAX_DISK_MB}MB limit")
        return used_mb

class CodeExecutionError(Exception):
    """Exception raised for code execution errors"""
    pass

class ResourceLimitExceeded(CodeExecutionError):
    """Exception raised when code exceeds resource limits"""
    pass

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

def run_code_in_sandbox(code: str, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute code in a restricted environment with resource limits"""
    is_safe, reason = analyze_code_safety(code)
    if not is_safe:
        return {
            "success": False,
            "error": f"Code safety check failed: {reason}",
            "output": None
        }

    monitor = ResourceMonitor()
    start_time = time.time()
    last_memory_check = start_time
    
    def check_resources():
        nonlocal last_memory_check
        current_time = time.time()
        
        # Check CPU time
        if current_time - start_time > MAX_CPU_TIME:
            raise ResourceLimitExceeded(f"CPU time exceeded {MAX_CPU_TIME} seconds")
            
        # Check memory periodically (every 0.5 seconds)
        if current_time - last_memory_check >= 0.5:
            monitor.check_memory_usage()
            monitor.check_disk_usage()
            last_memory_check = current_time
        
    # Check memory limit
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_MB * 1024 * 1024, -1))
    
    # Set CPU time limit
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_TIME, -1))

    # Create restricted globals
    safe_globals = {
        '__builtins__': {
            name: getattr(__builtins__, name)
            for name in ['abs', 'all', 'any', 'bin', 'bool', 'dict', 'float', 
                        'int', 'len', 'list', 'max', 'min', 'print', 'range', 
                        'round', 'str', 'sum', 'tuple']
        }
    }
    
    # Add any provided inputs to globals
    if inputs:
        safe_globals.update(inputs)
    
    try:
        # Capture stdout
        from io import StringIO
        output_buffer = StringIO()
        original_stdout = sys.stdout
        sys.stdout = output_buffer
        
        with timeout_handler(TIMEOUT_SECONDS):
            # Execute the code
            exec(code, safe_globals)
            
        output = output_buffer.getvalue()
        return {
            "success": True,
            "error": None,
            "output": output,
            "return_value": safe_globals.get('result', None)
        }
    
    except TimeoutError as e:
        return {
            "success": False,
            "error": str(e),
            "output": output_buffer.getvalue()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": output_buffer.getvalue()
        }
    finally:
        sys.stdout = original_stdout
