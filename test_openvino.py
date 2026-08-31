import sys
from unittest.mock import patch
from nexus_agent.cli.runtimes import _check_openvino

# Ensure it's imported first to match CI environment where pytest imports it
import openvino

def test_no_openvino():
    with patch.dict("sys.modules", {"openvino": None}):
        runtimes = _check_openvino()
        print(f"Runtimes length: {len(runtimes)}")
        if runtimes:
            print(f"Runtime content: {runtimes[0]}")

test_no_openvino()
