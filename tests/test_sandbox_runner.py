import pytest
from sandbox_runner import run_code_in_sandbox


def test_simple_print():
    code = 'print("hello")'
    res = run_code_in_sandbox(code)
    assert res["success"]
    # Depending on how you capture stdout, you might inspect res["output"]
    # If you only return return_value, adjust accordingly.


def test_infinite_loop():
    code = 'while True: pass'
    res = run_code_in_sandbox(code)
    assert not res["success"]
    assert "timed out" in res["error"].lower()


def test_forbidden_io(tmp_path):
    code = 'open("foo.txt","w").write("x")'
    res = run_code_in_sandbox(code)
    assert not res["success"]
    assert "not allowed" in res["error"].lower(
    ) or "file operations" in res["error"].lower()


def test_forbidden_import():
    code = 'import os'
    res = run_code_in_sandbox(code)
    assert not res["success"]
    assert "restricted module" in res["error"].lower()


def test_memory_exhaustion():
    # try to allocate a large list
    code = 'a = [0] * (10**8)'
    res = run_code_in_sandbox(code)
    assert not res["success"]
    assert "memory" in res["error"].lower() or "MemoryError" in res["error"]
