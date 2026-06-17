import sys

filepath = 'src/nexus_agent/cli/commands/agent_mixin.py'
with open(filepath, 'r') as f:
    content = f.read()

# Add missing Any import
old_import = "import time"
new_import = "import time\nfrom typing import Any"
if old_import in content:
    content = content.replace(old_import, new_import)

with open(filepath, 'w') as f:
    f.write(content)
print("Added Any import.")
