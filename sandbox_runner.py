import sys
import os
import ast
import builtins
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

def run_code(code: str, timeout: Optional[int] = 5) -> Dict[str, Any]:
    """
    Run code in a restricted environment
    Returns: Dict with success, output, and error information
    """
    try:
        # Parse and validate code
        tree = ast.parse(code)
        validate_ast(tree)

        # Prepare execution environment
        stdout = StringIO()
        stderr = StringIO()
        safe_globals = create_safe_globals()

        # Execute with redirected output
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(code, safe_globals, {})

        return {
            "success": True,
            "output": stdout.getvalue(),
            "error": stderr.getvalue() or None
        }

    except SandboxViolation as e:
        return {
            "success": False,
            "error": f"Security violation: {str(e)}",
            "output": None
        }
    except SyntaxError as e:
        return {
            "success": False,
            "error": f"Syntax error: {str(e)}",
            "output": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Runtime error: {str(e)}",
            "output": None
        }