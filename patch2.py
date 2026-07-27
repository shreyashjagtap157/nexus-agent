import re

with open('src/nexus_agent/gui/server.py', 'r') as f:
    content = f.read()

import_match2 = re.search(r'from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect', content)
if import_match2:
    print(import_match2.group(0))
