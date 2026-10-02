import unittest
from unittest.mock import patch, MagicMock

class RuntimeInfo:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def _check_openvino():
    runtimes = []
    try:
        import openvino
        runtimes.append(RuntimeInfo(
            name="OpenVINO", provider="openvino",
            available=True, path=openvino.__file__,
            description="Intel OpenVINO toolkit", priority=45,
        ))
    except ImportError:
        pass
    return runtimes

class TestCheckOpenvino(unittest.TestCase):
    def test_openvino_imported(self):
        with patch.dict("sys.modules", {"openvino": MagicMock(__file__="/path/openvino/__init__.py")}):
            runtimes = _check_openvino()
            self.assertEqual(len(runtimes), 1)

    def test_no_openvino(self):
        with patch.dict("sys.modules", {"openvino": None}):
            runtimes = _check_openvino()
            self.assertEqual(len(runtimes), 0)

if __name__ == "__main__":
    unittest.main()
