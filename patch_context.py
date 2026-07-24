with open("src/nexus_agent/core/project_context.py", "r") as f:
    content = f.read()

content = content.replace("from __future__ import annotations", "from __future__ import annotations\nimport os")

with open("src/nexus_agent/core/project_context.py", "w") as f:
    f.write(content)
