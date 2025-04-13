import sys
import os
import ast
import builtins
import subprocess
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Dict, Any, Optional
import resource
from datetime import datetime, timedelta

ALLOWED_BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytes', 'chr', 'dict', 
    'dir', 'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset',
    'hash', 'hex', 'int', 'isinstance', 'issubclass', 'len', 'list', 'map',
    'max', 'min', 'next', 'oct', 'ord', 'pow', 'print', 'range', 'repr',
    'reversed', 'round', 'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type',
    'zip'
}

RESTRICTED_NODES = {
    ast.Import, ast.ImportFrom,  # No imports
    ast.ClassDef,  # No class definitions
    ast.AsyncFunctionDef,  # No async functions
    ast.Await, ast.AsyncFor, ast.AsyncWith,  # No async operations
}

class SandboxViolation(Exception):
    pass

class SandboxException(Exception):
    pass

def validate_ast(node: ast.AST) -> bool:
    """Check if AST contains any restricted operations"""
    for child in ast.walk(node):
        if any(isinstance(child, restricted) for restricted in RESTRICTED_NODES):
            raise SandboxViolation(f"Restricted operation: {type(child).__name__}")
    return True

def create_safe_globals() -> Dict[str, Any]:
    """Create a restricted globals dict for code execution"""
    safe_globals = {
        name: getattr(builtins, name) 
        for name in ALLOWED_BUILTINS
    }
    return safe_globals

def run_code_in_sandbox(code, timeout=5):
    """
    Run code in a sandboxed environment with resource limits
    """
    try:
        # Create temp file for code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as code_file:
            code_file.write(code)
            code_file_path = code_file.name

        # Execute in subprocess with resource limits
        cmd = [
            "python3", "-c",
            f"import resource; " +
            f"resource.setrlimit(resource.RLIMIT_AS, (500*1024*1024, -1)); " +  # Memory: 500MB
            f"resource.setrlimit(resource.RLIMIT_CPU, (30, -1)); " +  # CPU: 30s
            f"resource.setrlimit(resource.RLIMIT_NPROC, (10, -1)); " +  # Processes: 10
            f"exec(open('{code_file_path}').read())"
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            success = proc.returncode == 0
            error = stderr if stderr else None
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            success = False
            error = "Execution timed out"

        os.unlink(code_file_path)

        return {
            "success": success,
            "output": stdout,
            "error": error
        }

    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e)
        }