import sys

content = open("src/nexus_agent/cli/commands/_base.py", "r").read()
# We need to type hint _term
if "from blessed import Terminal" in content:
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("_term ="):
            lines[i] = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\n_term: Terminal | None = Terminal() if Terminal else None"
            break
    open("src/nexus_agent/cli/commands/_base.py", "w").write("\n".join(lines) + "\n")
    print("Fixed type hint")
