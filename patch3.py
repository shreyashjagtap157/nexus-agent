import re

with open('src/nexus_agent/gui/server.py', 'r') as f:
    content = f.read()

import_match3 = re.search(r'@app.websocket\("/api/ws/\{session_id\}"\)\nasync def websocket_endpoint\(websocket: WebSocket, session_id: str\):\n    """WebSocket connection for real-time chat streaming and agent logs."""\n    await websocket.accept\(\)\n', content)
if import_match3:
    print(import_match3.group(0))
