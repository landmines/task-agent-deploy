# test_sandbox_runner.py
from sandbox_runner import run_in_sandbox

def test(code):
    result = run_in_sandbox(code)
    print("INPUT:")
    print(code)
    print("RESULT:")
    print(result)
    print("-" * 40)

if __name__ == "__main__":
    print("Running sandbox tests...\n")

    test("print('✅ Hello from safe code!')")
    test("x = 3 * 7\nprint(x)")
    test("import os\nprint(os.listdir())")
    test("open('file.txt', 'w')")
    test("print(sum([1, 2, 3, 4]))")
