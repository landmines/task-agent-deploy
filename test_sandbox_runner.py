import unittest
from sandbox_runner import run_code_in_sandbox, analyze_code_safety

class TestSandboxRunner(unittest.TestCase):
    def test_basic_execution(self):
        """Test basic code execution"""
        code = "result = 2 + 2"
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["return_value"], 4)

    def test_print_capture(self):
        """Test stdout capture"""
        code = "print('Hello World')"
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        self.assertIn("Hello World", result["output"])

    def test_restricted_modules(self):
        """Test restricted module imports"""
        code = "import os; os.system('ls')"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("restricted", result["error"].lower())

    def test_infinite_loop_timeout(self):
        """Test timeout on infinite loop"""
        code = "while True: pass"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())

    def test_syntax_error(self):
        """Test handling of syntax errors"""
        code = "this is not valid python"
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])

    def test_input_passing(self):
        """Test passing variables to sandbox"""
        code = "result = x + y"
        inputs = {"x": 5, "y": 3}
        result = run_code_in_sandbox(code, inputs)
        self.assertTrue(result["success"])
        self.assertEqual(result["return_value"], 8)

    def test_code_safety_analysis(self):
        """Test code safety analyzer"""
        safe_code = "x = 1 + 1"
        unsafe_code = "import subprocess; subprocess.run(['rm', '-rf', '/'])"

        self.assertTrue(analyze_code_safety(safe_code))
        self.assertFalse(analyze_code_safety(unsafe_code))

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

    def test_plan_tasks(self):
        """Test that the planner generates valid task sequences"""
        from planner import plan_tasks, validate_plan

        # Test app creation plan
        plan = plan_tasks("Create a new web app")
        self.assertTrue(validate_plan(plan))
        self.assertEqual(plan[0]["intent"], "create_app")

        # Test modification plan
        plan = plan_tasks("Update the database code")
        self.assertTrue(validate_plan(plan))
        self.assertEqual(plan[0]["intent"], "modify_file")

        # Test deploy plan
        plan = plan_tasks("Deploy my changes")
        self.assertTrue(validate_plan(plan))
        self.assertEqual(plan[0]["intent"], "run_tests")
        self.assertEqual(plan[1]["intent"], "deploy")

    def test_deployment_manager(self):
        """Test deployment management functionality"""
        from deployment_manager import DeploymentManager

        dm = DeploymentManager()

        # Test cost estimation
        costs = dm.estimate_deployment_cost({
            "compute_hours": 24,
            "storage_mb": 100,
            "bandwidth_mb": 1000
        })
        self.assertIsInstance(costs["total_cost"], float)
        self.assertTrue(costs["total_cost"] > 0)

        # Test deployment optimization
        config = {
            "memory_mb": 1024,
            "instances": 5,
            "storage_mb": 100
        }
        optimized = dm.optimize_deployment(config)
        self.assertLess(optimized["memory_mb"], config["memory_mb"])
        self.assertLess(optimized["instances"], config["instances"])

        # Test deployment and rollback
        deployment = dm.deploy(config)
        self.assertIn("timestamp", deployment)
        self.assertIn("config", deployment)
        self.assertIn("estimated_costs", deployment)

if __name__ == '__main__':
    unittest.main()