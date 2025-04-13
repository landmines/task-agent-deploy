
import unittest
from sandbox_runner import run_code, SandboxViolation

class TestSandboxRunner(unittest.TestCase):
    def test_basic_execution(self):
        code = "print('hello world')"
        result = run_code(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "hello world")
        
    def test_restricted_import(self):
        code = "import os\nprint(os.getcwd())"
        result = run_code(code)
        self.assertFalse(result["success"])
        self.assertIn("Security violation", result["error"])
        
    def test_restricted_class(self):
        code = "class Test: pass"
        result = run_code(code)
        self.assertFalse(result["success"])
        
    def test_syntax_error(self):
        code = "print('unclosed"
        result = run_code(code)
        self.assertFalse(result["success"])
        self.assertIn("Syntax error", result["error"])
        
    def test_runtime_error(self):
        code = "1/0"
        result = run_code(code)
        self.assertFalse(result["success"])
        self.assertIn("Runtime error", result["error"])

if __name__ == '__main__':
    unittest.main()
