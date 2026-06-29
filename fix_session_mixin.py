import sys

filepath = "src/nexus_agent/cli/commands/session_mixin.py"
with open(filepath, "r") as f:
    content = f.read()

# Add import itertools
content = content.replace("import os\n", "import os\nimport itertools\n")

# Replace greedy rglob
content = content.replace(
    '[str(f) for f in self.workspace.rglob("*.py")][:20]',
    'list(itertools.islice((str(f) for f in self.workspace.rglob("*.py")), 20))'
)

with open(filepath, "w") as f:
    f.write(content)
