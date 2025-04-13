
import json
import unittest
from sandbox_runner import run_code_in_sandbox
from task_executor import execute_task
from planner import validate_plan
from deployment_manager import DeploymentManager

class TaskAgentTests(unittest.TestCase):
    def setUp(self):
        with open('test_suite.json', 'r') as f:
            self.test_suite = json.load(f)
            
    def test_core_functionality(self):
        for test in self.test_suite['tests']:
            if test['intent'] == 'execute_code':
                result = run_code_in_sandbox(test['code'])
                self.assertEqual(result['success'], test['expected']['success'])
                if result['success']:
                    self.assertEqual(result['return_value'], test['expected']['return_value'])
                else:
                    self.assertIn(test['expected']['error'], result['error'].lower())
            else:
                result = execute_task({
                    'intent': test['intent'],
                    'task': test['task']
                })
                self.assertEqual(result['success'], test['expected']['success'])
                
    def test_deployment_validation(self):
        dm = DeploymentManager()
        result = dm.validate_deployment({
            'project_name': 'test-project',
            'provider': 'replit'
        })
        self.assertTrue(result['success'])

if __name__ == '__main__':
    unittest.main()
