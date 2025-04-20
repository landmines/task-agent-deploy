import os
import sys
import pytest

# allow import of file_ops.py from repo root
sys.path.insert(0,
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from file_ops import FileOps


def test_create_and_read(tmp_path):
    fn = tmp_path / "u.txt"
    res1 = FileOps.create_file(str(fn), "A\n")
    assert res1["success"]
    assert fn.read_text() == "A\n"


def test_append(tmp_path):
    fn = tmp_path / "u.txt"
    fn.write_text("X\n")
    res2 = FileOps.append_to_file(str(fn), "Y\n")
    assert res2["success"]
    assert fn.read_text().endswith("Y\n")


def test_insert_below(tmp_path):
    fn = tmp_path / "u.txt"
    fn.write_text("alpha\nbeta\n")
    res3 = FileOps.insert_below(str(fn), "alpha", "inserted")
    assert res3["success"]
    lines = fn.read_text().splitlines()
    assert lines[1] == "inserted"


def test_replace_line(tmp_path):
    fn = tmp_path / "u.txt"
    fn.write_text("old_line\nother\n")
    res4 = FileOps.replace_line(str(fn), "old_line", "new_line")
    assert res4["success"]
    assert fn.read_text().splitlines()[0] == "new_line"


def test_patch_code(tmp_path):
    fn = tmp_path / "u.py"
    fn.write_text("def foo():\n    pass\n")
    res5 = FileOps.patch_code(str(fn), "def foo():", "    # patched")
    assert res5["success"]
    lines = fn.read_text().splitlines()
    assert "# patched" in lines[1]


def test_delete_file(tmp_path):
    fn = tmp_path / "todelete.txt"
    fn.write_text("data")
    res6 = FileOps.delete_file(str(fn))
    assert res6["success"]
    assert not fn.exists()
