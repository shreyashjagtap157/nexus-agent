import re

file_path = "src/nexus_agent/cli/commands/agent_mixin.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the format properly. Python 3.10 compatible.
content = content.replace(
    'f"{\' \' * pad}{\'\\u2500\' * left_w}\\u252c{\'\\u2500\' * right_w}",',
    '(\' \' * pad) + (\'\\u2500\' * left_w) + \'\\u252c\' + (\'\\u2500\' * right_w),'
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
