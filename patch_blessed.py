import sys

filepath = 'src/nexus_agent/cli/commands/_base.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

search = """from blessed import Terminal"""

replace = """try:
    from blessed import Terminal
except ImportError:
    Terminal = None"""

if search in content:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.replace(search, replace))
    print("Success")
else:
    print("Failed to find search string")
