content = open("tests/nexus_agent/cli/test_input_handler_simple.py").read()
new_content = """import sys
from unittest.mock import MagicMock
sys.modules['blessed'] = MagicMock()
""" + content

with open("tests/nexus_agent/cli/test_input_handler_simple.py", "w") as f:
    f.write(new_content)
