import re

with open('src/nexus_agent/core/project_context.py', 'r') as f:
    content = f.read()

import_match = re.search(r'import logging', content)
if import_match:
    print(import_match.group(0))
