
import unittest
from sandbox_runner import run_code_in_sandbox, SandboxException

class TestSandboxRunner(unittest.TestCase):
    def test_basic_execution(self):
        code = "print('hello')"
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "hello")

    def test_execution_timeout(self):
        code = "while True: pass"
        result = run_code_in_sandbox(code, timeout=1)
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())

    def test_syntax_error(self):
        code = "print('hello'"  # Missing closing parenthesis
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("SyntaxError", result["error"])

    def test_restricted_imports(self):
        code = "import os; os.system('ls')"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("SecurityError", result["error"])

    def test_memory_limit(self):
        code = "x = [0] * 1000000000"  # Attempt to allocate large memory
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("MemoryError", result["error"])

    def test_file_access(self):
        code = "with open('test.txt', 'w') as f: f.write('test')"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("PermissionError", result["error"])

if __name__ == '__main__':
    unittest.main()
import unittest
from sandbox_runner import run_code_in_sandbox

class TestSandboxRunner(unittest.TestCase):
    def test_basic_execution(self):
        code = "print('Hello World')"
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "Hello World")

    def test_memory_limit(self):
        code = "x = [0] * (1024 * 1024 * 1000)"  # Try to allocate 1GB
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("MemoryError", str(result["error"]))

    def test_cpu_limit(self):
        code = "while True: pass"
        result = run_code_in_sandbox(code, timeout=2)
        self.assertFalse(result["success"])
        self.assertIn("timed out", str(result["error"]).lower())

    def test_process_limit(self):
        code = """
import multiprocessing
processes = []
for i in range(100):
    p = multiprocessing.Process(target=lambda: None)
    p.start()
    processes.append(p)
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])

if __name__ == '__main__':
    unittest.main()
