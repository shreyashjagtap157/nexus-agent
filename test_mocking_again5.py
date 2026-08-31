import sys
import pytest

from nexus_agent.cli.runtimes import _check_openvino
from unittest.mock import patch

def test_no_openvino():
    # If openvino isn't imported normally but maybe from another module?
    with patch.dict("sys.modules", {"openvino": None}):
        runtimes = _check_openvino()
        print(len(runtimes))

test_no_openvino()
