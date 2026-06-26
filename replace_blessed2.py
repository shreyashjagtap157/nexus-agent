import sys

def replace_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # The error is 'ModuleNotFoundError: No module named 'blessed'' in tests
    # Let's add a sys mock for it in tests/nexus_agent/cli/test_input_handler_simple.py

    if filepath == 'tests/nexus_agent/cli/test_input_handler_simple.py':
        # Add noqa: E402
        content = content.replace("import unittest", "import unittest  # noqa: E402")
        content = content.replace("from unittest.mock import MagicMock, patch", "from unittest.mock import MagicMock, patch  # noqa: E402")
        content = content.replace("from nexus_agent.cli.input_handler_simple import MinimalInputHandlerMixin", "from nexus_agent.cli.input_handler_simple import MinimalInputHandlerMixin  # noqa: E402")

    with open(filepath, 'w') as f:
        f.write(content)

replace_in_file('tests/nexus_agent/cli/test_input_handler_simple.py')
