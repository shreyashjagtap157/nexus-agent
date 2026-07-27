import re

with open('src/nexus_agent/gui/server.py', 'r') as f:
    content = f.read()

print("Original app.websocket signature:")
match = re.search(r'@app.websocket[^\n]*\nasync def websocket_endpoint[^\n]*\n', content)
if match:
    print(match.group(0))

print("Original imports:")
import_match = re.search(r'import json\nimport logging\nimport socket\nimport subprocess\nimport threading\nimport time\nimport webbrowser', content)
if import_match:
    print(import_match.group(0))
