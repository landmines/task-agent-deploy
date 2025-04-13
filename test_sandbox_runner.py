
import unittest
from sandbox_runner import run_code_in_sandbox, check_ast_safety, TimeoutError

class TestSandboxRunner(unittest.TestCase):
    def test_basic_execution(self):
        code = "print('hello world')"
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "hello world")
    
    def test_timeout(self):
        code = "while True: pass"
        result = run_code_in_sandbox(code, timeout_seconds=1)
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())
    
    def test_blocked_imports(self):
        code = "import os"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["error"])
    
    def test_blocked_file_operations(self):
        code = "open('test.txt', 'w')"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["error"])
    
    def test_allowed_operations(self):
        code = """
x = [1, 2, 3, 4, 5]
print(sum(x))
print(len(x))
print(max(x))
"""
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        output_lines = result["output"].strip().split('\n')
        self.assertEqual(output_lines, ['15', '5', '5'])

if __name__ == '__main__':
    unittest.main()
