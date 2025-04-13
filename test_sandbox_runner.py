import unittest
from sandbox_runner import run_code_in_sandbox, ResourceMonitor, ResourceLimitExceeded

class TestSandboxRunner(unittest.TestCase):
    def test_basic_execution(self):
        """Test basic code execution"""
        code = """
x = 1 + 1
print(x)
result = x
"""
        result = run_code_in_sandbox(code)
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "2")
        self.assertEqual(result["return_value"], 2)

    def test_memory_limit(self):
        """Test memory limit enforcement"""
        code = """
x = bytearray(300 * 1024 * 1024)  # Try to allocate 300MB
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("memory", result["error"].lower())

    def test_cpu_limit(self):
        """Test CPU time limit"""
        code = """
while True: pass
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("time", result["error"].lower())

    def test_restricted_imports(self):
        """Test restricted module imports"""
        code = """
import os
os.system('ls')
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("restricted", result["error"].lower())

    def test_file_system_access(self):
        """Test file system restrictions"""
        code = """
with open('test.txt', 'w') as f:
    f.write('test')
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("restricted", result["error"].lower())

    def test_resource_monitor(self):
        """Test resource monitoring functionality"""
        monitor = ResourceMonitor()

        # Test memory check
        memory_usage = monitor.check_memory_usage()
        self.assertIsInstance(memory_usage, float)
        self.assertGreater(memory_usage, 0)

        # Test CPU time check
        cpu_time = monitor.check_cpu_time()
        self.assertIsInstance(cpu_time, float)
        self.assertGreaterEqual(cpu_time, 0)

        # Test disk usage check
        disk_usage = monitor.check_disk_usage()
        self.assertIsInstance(disk_usage, float)
        self.assertGreater(disk_usage, 0)


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

        # Test free tier usage
        free_resources = {
            "compute_hours": 100,
            "storage_mb": 200,
            "bandwidth_mb": 50000
        }
        estimate = dm.estimate_deployment_cost(free_resources)
        self.assertTrue(estimate["within_free_tier"])
        self.assertEqual(estimate["total_cost"], 0)

        # Test paid tier usage
        paid_resources = {
            "compute_hours": 1000,
            "storage_mb": 1000,
            "bandwidth_mb": 150000
        }
        estimate = dm.estimate_deployment_cost(paid_resources)
        self.assertFalse(estimate["within_free_tier"])
        self.assertGreater(estimate["total_cost"], 0)

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

    def test_resource_limits(self):
        """Test that resource limits are enforced"""
        # Test memory limit
        memory_heavy_code = "x = ' ' * (1024 * 1024 * 1000)"  # Try to allocate 1GB
        result = run_code_in_sandbox(memory_heavy_code)
        self.assertFalse(result["success"])
        self.assertIn("memory", result["error"].lower())

        # Test CPU limit
        cpu_heavy_code = "while True: pass"
        result = run_code_in_sandbox(cpu_heavy_code)
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())

    def test_file_operations(self):
        """Test that file operations are blocked"""
        file_op_code = "with open('test.txt', 'w') as f: f.write('test')"
        result = run_code_in_sandbox(file_op_code)
        self.assertFalse(result["success"])
        self.assertIn("file operations not allowed", result["error"].lower())

    def test_safe_execution(self):
        """Test that safe code executes properly"""
        safe_code = "x = [i * 2 for i in range(10)]; result = sum(x)"
        result = run_code_in_sandbox(safe_code)
        self.assertTrue(result["success"])
        self.assertEqual(result["return_value"], 90)

    def test_run_code_in_sandbox(self):
        # Test basic code execution
        result = run_code_in_sandbox("print('test')")
        self.assertTrue(result["success"])
        self.assertIn("test", result["output"])

        # Test memory limit
        code = """
x = [1] * (1024 * 1024 * 300)  # Try to allocate ~300MB
print(len(x))
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("Memory usage exceeded", result["error"])

        # Test CPU limit
        code = """
while True:
    pass
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("CPU time exceeded", result["error"])

        # Test restricted modules
        code = """
import subprocess
subprocess.run(['ls'])
"""
        result = run_code_in_sandbox(code)
        self.assertFalse(result["success"])
        self.assertIn("Restricted module", result["error"])


if __name__ == '__main__':
    unittest.main()