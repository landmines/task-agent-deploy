
import sys
import ast
import builtins
from io import StringIO
from contextlib import contextmanager
import threading
import _thread
import time

ALLOWED_BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytes', 'chr', 'dict', 
    'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset', 'hash', 
    'hex', 'int', 'isinstance', 'issubclass', 'len', 'list', 'map', 'max',
    'min', 'next', 'oct', 'ord', 'pow', 'print', 'range', 'repr', 'reversed',
    'round', 'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip'
}

class TimeoutError(Exception):
    pass

def timeout_handler():
    _thread.interrupt_main()

@contextmanager
def timeout(seconds):
    timer = threading.Timer(seconds, timeout_handler)
    timer.start()
    try:
        yield
    except KeyboardInterrupt:
        raise TimeoutError(f"Code execution timed out after {seconds} seconds")
    finally:
        timer.cancel()

def check_ast_safety(code_str):
    """Check if the AST contains potentially dangerous operations"""
    tree = ast.parse(code_str)
    
    for node in ast.walk(tree):
        # Block imports
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            raise ValueError("Import statements are not allowed in sandbox")
        
        # Block file operations
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ['open', 'eval', 'exec', 'compile']:
                    raise ValueError(f"Function '{node.func.id}' is not allowed in sandbox")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in ['read', 'write', 'open', 'system']:
                    raise ValueError(f"Method '{node.func.attr}' is not allowed in sandbox")

    return True

def create_safe_globals():
    """Create a restricted globals dictionary for code execution"""
    safe_globals = {
        '__builtins__': {name: getattr(builtins, name) for name in ALLOWED_BUILTINS}
    }
    return safe_globals

def run_code_in_sandbox(code_str, timeout_seconds=5):
    """Execute code in a restricted environment with timeout"""
    output_buffer = StringIO()
    
    try:
        check_ast_safety(code_str)
        safe_globals = create_safe_globals()
        
        # Redirect stdout to capture output
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        
        try:
            with timeout(timeout_seconds):
                exec(code_str, safe_globals, {})
        finally:
            sys.stdout = old_stdout
            
        return {
            "success": True,
            "output": output_buffer.getvalue(),
            "error": None
        }
        
    except TimeoutError as e:
        return {
            "success": False,
            "output": output_buffer.getvalue(),
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "output": output_buffer.getvalue(),
            "error": str(e)
        }
