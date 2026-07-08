import sys

filepath = "src/nexus_agent/cli/commands/agent_mixin.py"

with open(filepath, "r") as f:
    content = f.read()

target = """f"{' ' * PAD}{chr(0x2500) * left_w}{chr(0x252c)}{chr(0x2500) * right_w}","""

replacement = """f"{' ' * PAD}{chr(0x2500) * left_w}{chr(0x252c)}{chr(0x2500) * right_w}","""

if "f-string expression part cannot include a backslash" in content:
    # Not actually here, wait, the error happened on line 127 of tests/nexus_agent/cli/commands/test_interactive_ui.py ?? No, agent_mixin.py
    pass
