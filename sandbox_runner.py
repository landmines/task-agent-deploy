
import ast
import sys
from typing import Dict, Any
import traceback
from datetime import datetime, UTC

def is_safe_ast(tree: ast.AST) -> bool:
    """Check if AST contains only allowed operations"""
    dangerous_calls = {'eval', 'exec', 'compile', 'open', 'file',
                      '__import__', 'input', 'raw_input'}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_calls:
                    return False
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_calls:
                    return False
    return True

def create_safe_globals() -> Dict[str, Any]:
    """Create a restricted globals dict for code execution"""
    safe_builtins = {
        'abs': abs, 'bool': bool, 'int': int, 'float': float, 
        'len': len, 'list': list, 'dict': dict, 'max': max,
        'min': min, 'print': print, 'range': range, 'str': str,
        'sum': sum, 'tuple': tuple
    }
    return {
        '__builtins__': safe_builtins,
        'datetime': datetime,
        'UTC': UTC
    }

def run_code_in_sandbox(code: str, timeout: int = 5) -> Dict[str, Any]:
    """Execute code in a restricted environment"""
    try:
        tree = ast.parse(code)
        if not is_safe_ast(tree):
            return {
                'success': False,
                'error': 'Code contains unsafe operations',
                'output': None
            }

        globals_dict = create_safe_globals()
        locals_dict = {}

        exec(code, globals_dict, locals_dict)
        
        return {
            'success': True,
            'error': None,
            'output': locals_dict.get('result', None)
        }

    except SyntaxError as e:
        return {
            'success': False,
            'error': f'Syntax error: {str(e)}',
            'output': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Execution error: {str(e)}',
            'traceback': traceback.format_exc(),
            'output': None
        }
