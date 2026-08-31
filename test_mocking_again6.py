import sys
from unittest.mock import patch, MagicMock

# Simulate what pytest does? No, let's see why checking OpenVINO doesn't raise ImportError
# even when `sys.modules['openvino'] = None`.

# Could there be another mock interfering in the test suite?
import tests.nexus_agent.cli.test_runtimes

def test_no_openvino():
    test_case = tests.nexus_agent.cli.test_runtimes.TestCheckOpenvino('test_no_openvino')
    test_case.test_no_openvino()

test_no_openvino()
