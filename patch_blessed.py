import re

with open('src/nexus_agent/cli/commands/_base.py', 'r') as f:
    content = f.read()

import_match = re.search(r'from blessed import Terminal\n\n_term = Terminal\(\)', content)
if import_match:
    print(import_match.group(0))
