with open("tests/nexus_agent/cli/test_runtimes.py", "r") as f:
    content = f.read()

import_blocker = """
class ImportBlocker:
    def __init__(self, *module_names):
        self.module_names = module_names

    def find_spec(self, fullname, path, target=None):
        if fullname in self.module_names:
            raise ImportError(f"No module named '{fullname}'")
        return None
"""

new_content = content.replace("class TestCheckOpenvino(unittest.TestCase):", import_blocker + "\nclass TestCheckOpenvino(unittest.TestCase):")

import_sys = "import sys\nfrom unittest.mock import MagicMock, patch"
new_content = new_content.replace("from unittest.mock import MagicMock, patch", import_sys)


new_content = new_content.replace(
    """    def test_no_openvino(self):
        with patch.dict("sys.modules", {"openvino": None}):
            runtimes = _check_openvino()
            self.assertEqual(len(runtimes), 0)""",
    """    def test_no_openvino(self):
        with patch("sys.meta_path", [ImportBlocker("openvino")] + sys.meta_path):
            runtimes = _check_openvino()
            self.assertEqual(len(runtimes), 0)"""
)

with open("tests/nexus_agent/cli/test_runtimes.py", "w") as f:
    f.write(new_content)
