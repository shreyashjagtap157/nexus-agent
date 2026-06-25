import tempfile
from pathlib import Path

from nexus_agent.utils.fs import fast_rglob


def test_fast_rglob_basic():
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)

        # Create some files
        (dir_path / "test1.py").touch()
        (dir_path / "test2.txt").touch()

        sub_dir = dir_path / "sub"
        sub_dir.mkdir()
        (sub_dir / "test3.py").touch()
        (sub_dir / "test4.md").touch()

        # Test *.py
        py_files = list(fast_rglob(dir_path, "*.py"))
        assert len(py_files) == 2
        assert any(f.name == "test1.py" for f in py_files)
        assert any(f.name == "test3.py" for f in py_files)

        # Test exact match not supported currently without fnmatch catchall
        txt_files = list(fast_rglob(dir_path, "*.txt"))
        assert len(txt_files) == 1
        assert txt_files[0].name == "test2.txt"


def test_fast_rglob_substring():
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        (dir_path / "my_test_file.py").touch()
        (dir_path / "other_file.py").touch()

        # Test *test*
        test_files = list(fast_rglob(dir_path, "*test*"))
        assert len(test_files) == 1
        assert test_files[0].name == "my_test_file.py"
