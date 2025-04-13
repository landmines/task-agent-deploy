import sys
import os
import ast
import builtins
import subprocess
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Dict, Any, Optional

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
    """Execute code in sandbox environment with security restrictions"""
    restricted_imports = ["os", "subprocess", "sys", "builtins"]
    restricted_builtins = ["eval", "exec", "__import__"]

    # Check for restricted imports
    for imp in restricted_imports:
        if f"import {imp}" in code or f"from {imp}" in code:
            return {
                "success": False,
                "error": "SecurityError: Restricted import attempted",
                "output": None
            }

    # Check for restricted builtins
    for builtin in restricted_builtins:
        if builtin in code:
            return {
                "success": False,
                "error": "SecurityError: Restricted builtin usage attempted",
                "output": None
            }

    try:
        # Create a secure temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to a temporary file
            code_file = os.path.join(tmpdir, "code.py")
            with open(code_file, "w") as f:
                f.write(code)

            # Run with resource limits
            cmd = [
                "python3", "-c",
                f"import resource; " +
                f"resource.setrlimit(resource.RLIMIT_AS, (500*1024*1024, -1)); " +  # Memory limit: 500MB
                f"resource.setrlimit(resource.RLIMIT_CPU, (30, -1)); " +  # CPU time limit: 30 seconds
                f"resource.setrlimit(resource.RLIMIT_NPROC, (50, -1)); " +  # Process limit: 50
                f"exec(open('{code_file}').read())"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Execution timed out",
            "output": None
        }
    except MemoryError:
        return {
            "success": False,
            "error": "MemoryError: Exceeded memory limit",
            "output": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": None
        }