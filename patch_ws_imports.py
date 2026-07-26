import re

with open("tests/test_websocket_cswsh.py", "r") as f:
    content = f.read()

# E402 Module level import not at top of file
content = content.replace("import pytest\nfrom fastapi.testclient import TestClient\nfrom starlette.websockets import WebSocketDisconnect\n\nfrom nexus_agent.gui.server import app", "import pytest  # noqa: E402\nfrom fastapi.testclient import TestClient  # noqa: E402\nfrom starlette.websockets import WebSocketDisconnect  # noqa: E402\n\nfrom nexus_agent.gui.server import app  # noqa: E402")

with open("tests/test_websocket_cswsh.py", "w") as f:
    f.write(content)
