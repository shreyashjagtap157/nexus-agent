import urllib.parse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, WebSocketException
from fastapi.testclient import TestClient
import uvicorn
import asyncio
from starlette.websockets import WebSocketDisconnect as StarletteDisconnect

app = FastAPI()

@app.websocket("/api/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Retrieve Host and Origin headers
    origin = websocket.headers.get("origin")
    host_header = websocket.headers.get("host")

    # CSWSH protection logic
    if origin is not None:
        if origin == "null":
            raise WebSocketException(code=403, reason="Forbidden: Origin null not allowed")

        parsed_origin = urllib.parse.urlparse(origin)
        origin_hostname = parsed_origin.hostname

        if not host_header:
            raise WebSocketException(code=403, reason="Forbidden: Missing Host header")

        if host_header.startswith('['):
            host_hostname = host_header[1:host_header.find(']')]
        else:
            host_hostname = host_header.split(':')[0]

        if origin_hostname != host_hostname:
            raise WebSocketException(code=403, reason="Forbidden: Cross-Site WebSocket Hijacking")

    await websocket.accept()
    try:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
    except StarletteDisconnect:
        pass

client = TestClient(app)

def test_websocket():
    # Test valid origin
    with client.websocket_connect("/api/ws/123", headers={"origin": "http://testserver", "host": "testserver"}) as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        print("Valid Origin:", data)

    # Test missing origin (programmatic client)
    with client.websocket_connect("/api/ws/123", headers={"host": "testserver"}) as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        print("No Origin:", data)

    # Test cross-origin
    try:
        with client.websocket_connect("/api/ws/123", headers={"origin": "http://evil.com", "host": "testserver"}) as websocket:
            websocket.send_text("Hello")
            data = websocket.receive_text()
    except Exception as e:
        print("Cross Origin Exception:", type(e))

test_websocket()
