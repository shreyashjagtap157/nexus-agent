import sys

def replace_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # The error is 'ModuleNotFoundError: No module named 'blessed'' in tests
    # Let's add a sys mock for it in tests/nexus_agent/cli/test_input_handler_simple.py

    if filepath == 'tests/nexus_agent/cli/test_input_handler_simple.py':
        # Add mock at the top
        new_content = "import sys\nfrom unittest.mock import MagicMock\nsys.modules['blessed'] = MagicMock()\n\n" + content
        content = new_content

    with open(filepath, 'w') as f:
        f.write(content)

replace_in_file('tests/nexus_agent/cli/test_input_handler_simple.py')
