
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

    def test_file_system_access(self):
        code = """
import os
os.system('touch test.txt')
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])

if __name__ == '__main__':
    unittest.main()
